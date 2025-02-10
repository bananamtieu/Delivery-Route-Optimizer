import React, { useState, useEffect } from "react";
import axios from "axios";
import DeliveryMap from "./DeliveryMap"; // Import the DeliveryMap component
import "./App.css";

const API_URL = "http://127.0.0.1:5000";
const GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY";

const App = () => {
    const [depot, setDepot] = useState(null);
    const [depotAddress, setDepotAddress] = useState("");
    const [deliveries, setDeliveries] = useState([]);
    const [address, setAddress] = useState("");
    const [demand, setDemand] = useState(1);
    const [routes, setRoutes] = useState([]);
    const [map, setMap] = useState(null);
    const [markers, setMarkers] = useState({ depot: null, deliveries: [] });

    useEffect(() => {
        fetchDepot();
        fetchDeliveries();
    }, []);

    const handleInputChange = (field, value) => {
        if (field === "depotAddress") setDepotAddress(value);
        if (field === "address") setAddress(value);
    };

    // Fetch depot location from backend
    const fetchDepot = async () => {
        try {
            const response = await axios.get(`${API_URL}/get_depot`);
            if (response.data.depot) {
                setDepot(response.data.depot);
            }
        } catch (error) {
            console.error("Error fetching depot:", error);
        }
    };

    // Fetch deliveries from backend
    const fetchDeliveries = async () => {
        try {
            const response = await axios.get(`${API_URL}/deliveries`);
            setDeliveries(response.data.deliveries);
        } catch (error) {
            console.error("Error fetching deliveries:", error);
        }
    };

    // Set depot location
    const handleSetDepot = async () => {
        if (!depotAddress) {
            alert("Please enter a valid depot address.");
            return;
        }

        try {
            const response = await axios.get("https://maps.googleapis.com/maps/api/geocode/json", {
                params: { address: depotAddress, key: GOOGLE_MAPS_API_KEY },
            });

            if (response.data.status === "OK") {
                const { lat, lng } = response.data.results[0].geometry.location;
                const newDepot = { latitude: lat, longitude: lng, address: depotAddress };

                setDepot(newDepot);

                await axios.post(`${API_URL}/set_depot`, {
                    latitude: lat,
                    longitude: lng,
                    address: depotAddress,
                });

                setDepotAddress("");
            } else {
                alert("Failed to fetch coordinates. Please check the address and try again.");
            }
        } catch (error) {
            console.error("Error setting depot:", error);
        }
    };

    // Add a new delivery
    const addDelivery = async () => {
        if (!address) {
            alert("Please enter a valid address.");
            return;
        }

        try {
            await axios.post(`${API_URL}/add_delivery`, { address, demand });
            fetchDeliveries();
            setAddress("");
            setDemand(1);
        } catch (error) {
            console.error("Error adding delivery:", error);
        }
    };

    // Optimize delivery routes
    const optimizeRoutes = async () => {
        if (!depot) {
            alert("Please set the depot location before optimizing routes!");
            return;
        }

        try {
            const response = await axios.post(`${API_URL}/optimize_routes`, { num_vehicles: 4, depot });
            setRoutes(response.data.optimized_routes);
        } catch (error) {
            console.error("Error optimizing routes:", error);
        }
    };

    // Utility function to create a marker
    const createMarker = (map, position, title, iconUrl) => {
        return new window.google.maps.Marker({
            position,
            map,
            title,
            icon: { url: iconUrl },
        });
    };

    // Update markers dynamically
    useEffect(() => {
        if (map && depot && window.google) {
            // Update depot marker
            if (markers.depot) markers.depot.setMap(null);
            const depotMarker = createMarker(
                map,
                { lat: depot.latitude, lng: depot.longitude },
                "Depot",
                "http://maps.google.com/mapfiles/ms/icons/blue-dot.png"
            );
            setMarkers((prev) => ({ ...prev, depot: depotMarker }));

            // Clear existing route Polylines
            setRoutes([]); // Clear routes state

            map.panTo({ lat: depot.latitude, lng: depot.longitude });
        }
    }, [map, depot]);

    useEffect(() => {
        if (map && deliveries.length > 0 && window.google) {
            // Clear existing delivery markers
            markers.deliveries.forEach((marker) => marker.setMap(null));
            const deliveryMarkers = deliveries.map((delivery) =>
                createMarker(
                    map,
                    { lat: delivery.latitude, lng: delivery.longitude },
                    delivery.address,
                    "http://maps.google.com/mapfiles/ms/icons/red-dot.png"
                )
            );
            setMarkers((prev) => ({ ...prev, deliveries: deliveryMarkers }));

            // Clear existing route Polylines
            setRoutes([]); // Clear routes state
        }
    }, [map, deliveries]);

    // Input and button components for reuse
    const Input = ({ placeholder, value, onChange }) => (
        <input type="text" placeholder={placeholder} value={value} onChange={onChange} className="input" />
    );

    const Button = ({ onClick, children }) => <button onClick={onClick} className="button">{children}</button>;

    return (
        <div className="app-header">
            <h1>Delivery Route Optimizer</h1>
            <div className="layout-container">
                <DeliveryMap depot={depot} routes={routes} deliveries={deliveries} onMapLoad={setMap} />
                <div className="controls-container">
                    <div className="control-section">
                        <h2>Set Depot</h2>
                        <Input
                            placeholder="Enter depot address"
                            value={depotAddress}
                            onChange={(e) => handleInputChange("depotAddress", e.target.value)}
                        />
                        <Button onClick={handleSetDepot}>Set Depot</Button>
                    </div>
                    <div className="control-section">
                        <h2>Add Delivery</h2>
                        <Input
                            placeholder="Enter delivery address"
                            value={address}
                            onChange={(e) => handleInputChange("address", e.target.value)}
                        />
                        <Input
                            placeholder="Enter delivery demand (e.g., 1)"
                            value={demand}
                            onChange={(e) => setDemand(parseInt(e.target.value) || 1)}
                        />
                        <Button onClick={addDelivery}>Add Delivery</Button>
                    </div>
                    <Button onClick={optimizeRoutes}>Optimize Routes</Button>
                </div>
            </div>
        </div>
    );
};

export default App;
