from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Import CORS
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
import requests
import googlemaps

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database configuration
DB_NAME = "route_optimization"
DB_USER = "postgres"
DB_PASSWORD = "your_password"  # Replace with your actual password
DB_HOST = "localhost"
DB_PORT = "5432"

# Google Maps API Key
API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"
gmaps = googlemaps.Client(key=API_KEY)

app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Define the Deliveries model
class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    demand = db.Column(db.Integer, nullable=False, default=1)  # Default demand = 1
    is_depot = db.Column(db.Boolean, nullable=False, default=False)  # New column to identify the depot

# Define the Vehicle Routes model
class VehicleRoute(db.Model):
    vehicle_id = db.Column(db.Integer, primary_key=True)
    route = db.Column(db.Text, nullable=False)

# Route to check if API is running
@app.route("/")
def home():
    return jsonify({"message": "Flask API for Route Optimization is running!"})

# Retrieves the latitude and longitude of a given address using the Google Maps Geocoding API
def get_coordinates(address):
    response = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params={"address": address, "key": API_KEY})
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "OK" and data["results"]:
            return data["results"][0]["geometry"]["location"]
    return None  # Return None if the request fails

@app.route("/set_depot", methods=["POST"])
def set_depot():
    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    address = data.get("address")

    if not latitude or not longitude or not address:
        return jsonify({"error": "Latitude, longitude, and address are required"}), 400

    # Check if a depot already exists
    depot = Delivery.query.filter_by(is_depot=True).first()
    if depot:
        # Update existing depot
        depot.latitude = latitude
        depot.longitude = longitude
        depot.address = address
    else:
        # Create a new depot
        depot = Delivery(
            address=address,
            latitude=latitude,
            longitude=longitude,
            is_depot=True
        )
        db.session.add(depot)

    db.session.query(VehicleRoute).delete()
    db.session.commit()
    return jsonify({"message": "Depot location saved successfully!"})

@app.route("/get_depot", methods=["GET"])
def get_depot():
    depot = Delivery.query.filter_by(is_depot=True).first()
    if depot:
        return jsonify({
            "depot": {
                "address": depot.address,
                "latitude": depot.latitude,
                "longitude": depot.longitude
            }
        })
    else:
        return jsonify({"depot": None})  # Return None if no depot exists

# Route to add delivery locations
@app.route("/add_delivery", methods=["POST"])
def add_delivery():
    data = request.json
    coordinates = get_coordinates(data["address"])
    new_delivery = Delivery(
        address = data["address"],
        latitude = coordinates['lat'],
        longitude = coordinates['lng'],
        demand = data.get("demand", 1),  # Default demand = 1
    )
    db.session.add(new_delivery)
    db.session.commit()
    return jsonify({"message": "Delivery added successfully!"})

# Route to fetch all deliveries
@app.route("/deliveries", methods=["GET"])
def get_deliveries():
    deliveries = Delivery.query.filter_by(is_depot=False).all()
    return jsonify({
        "deliveries": [
            {
                "id": delivery.id,
                "address": delivery.address,
                "latitude": delivery.latitude,
                "longitude": delivery.longitude,
                "demand": delivery.demand
            } for delivery in deliveries
        ]
    })

def compute_distance_matrix():
    depot = Delivery.query.filter_by(is_depot=True).first()
    if not depot:
        raise ValueError("Depot location is not set!")

    deliveries = Delivery.query.filter_by(is_depot=False).all()
    coordinates = [(depot.latitude, depot.longitude)] + [
        (delivery.latitude, delivery.longitude) for delivery in deliveries
    ]

    num_locations = len(coordinates)
    batch_size = 10  # API limit approximation

    def get_batch(origins, destinations):
        response = gmaps.distance_matrix(origins, destinations, mode="driving")
        return response["rows"]

    # Build distance matrix in batches
    matrix = [[0] * num_locations for _ in range(num_locations)]
    for i in range(0, num_locations, batch_size):
        for j in range(0, num_locations, batch_size):
            batch_result = get_batch(coordinates[i:i+batch_size], coordinates[j:j+batch_size])
            for origin_idx, row in enumerate(batch_result):
                for dest_idx, element in enumerate(row["elements"]):
                    matrix[i + origin_idx][j + dest_idx] = element["distance"]["value"]
    return matrix

# Function to solve VRP
def solve_vrp(distance_matrix, num_vehicles):
    deliveries = Delivery.query.filter_by(is_depot=False).all()
    demands = [0] + [delivery.demand for delivery in deliveries]  # Include depot demand (0)
    vehicle_capacities = [15, 20, 25, 10]  # Example capacities for 4 vehicles

    num_locations = len(distance_matrix)
    depot = 0  # The depot (starting point for all vehicles)

    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)

    # Create and register a transit callback.
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Distance constraint
    dimension_name = "Distance"
    routing.AddDimension(
        transit_callback_index,
        0,  # No slack
        100000,  # Maximum travel distance per vehicle
        True,  # Start cumul to zero
        dimension_name,
    )
    distance_dimension = routing.GetDimensionOrDie(dimension_name)
    distance_dimension.SetGlobalSpanCostCoefficient(100)

    # Add Capacity constraint.
    def demand_callback(from_index):
        """Returns the demand of the node."""
        # Convert from routing variable Index to demands NodeIndex.
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        vehicle_capacities,  # vehicle maximum capacities
        True,  # start cumul to zero
        "Capacity",
    )

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(1)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    # Extract the solution
    if solution:
        routes = []
        for vehicle_id in range(num_vehicles):
            route = []
            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                route.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))
            route.append(manager.IndexToNode(index))  # Add depot
            routes.append(route)
        return routes  # Return raw Python list
    else:
        return None  # Return None if no solution found

# Route to optimize routes
@app.route("/optimize_routes", methods=["POST"])
def optimize_routes():
    data = request.json
    num_vehicles = data.get("num_vehicles", 1)

    # Compute distance matrix with the depot as the first location
    distance_matrix = compute_distance_matrix()
    # print(distance_matrix)
    routes = solve_vrp(distance_matrix, num_vehicles)

    # Clear the vehicle_route table
    db.session.query(VehicleRoute).delete()
    db.session.commit()

    if not routes:
        return jsonify({"error": "No optimized routes found."}), 400

    # Insert new routes
    for vehicle_id, op_r in enumerate(routes):
        db.session.add(VehicleRoute(vehicle_id=vehicle_id + 1, route=str(op_r)))
    db.session.commit()

    return jsonify({"optimized_routes": routes})

# Route to get optimized routes
@app.route("/get_routes", methods=["GET"])
def get_routes():
    routes = VehicleRoute.query.all()
    output = [{"vehicle_id": route.vehicle_id, "route": route.route} for route in routes]
    return jsonify({"routes": output})

# Run Flask app
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensure tables are created
    app.run(debug=True)
