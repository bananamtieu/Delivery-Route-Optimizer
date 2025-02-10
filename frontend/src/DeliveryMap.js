import React from "react";
import { GoogleMap, LoadScript, Marker, Polyline } from "@react-google-maps/api";

const GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY";

const colors = ["#FF0000", "#00FF00", "#0000FF", "#FFA500", "#800080",
    "#FFFF00", "#00FFFF", "#FFC0CB", "#808080", "#8B0000"]; // Add more colors as needed

const DeliveryMap = ({ depot, routes, deliveries, onMapLoad }) => {
    const defaultCenter = { lat: 40.7128, lng: -74.0060 }; // Default center (e.g., New York)

    return (
        <LoadScript googleMapsApiKey={GOOGLE_MAPS_API_KEY}>
            <GoogleMap
                mapContainerClassName="map-container"
                center={depot ? { lat: depot.latitude, lng: depot.longitude } : defaultCenter}
                zoom={10}
                onLoad={onMapLoad}
            >
                {depot && routes.map((route, index) => {
                    const path = route.map((nodeIndex) => {
                        if (nodeIndex === 0) return { lat: depot.latitude, lng: depot.longitude }; // Depot location
                        const delivery = deliveries[nodeIndex - 1]; // Adjust for 1-based indexing
                        return delivery
                            ? { lat: delivery.latitude, lng: delivery.longitude }
                            : null;
                    })
                    .filter(Boolean); // Remove null values
                    return (
                        <Polyline
                            key={index}
                            path={path}
                            options={{
                                strokeColor: colors[index % colors.length], // Cycle through colors
                                strokeWeight: 2,
                            }}
                        />
                    );
                })}
            </GoogleMap>
        </LoadScript>
    );
};

export default DeliveryMap;
