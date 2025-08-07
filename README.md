# 🚀 Auto Order Assignment System

This project automates the rider assignment of delivery orders to nearby available riders using real-time geolocation, estimated travel time, and food preparation duration. It integrates Google Maps APIs, a MySQL database, and a Flask API server. The system also generates a visual map of assigned orders using Folium.


- Assigning orders to the nearest available delivery rider
- Estimating preparation time for food items
- Sending rider and user notifications
- Providing optimized Google Maps route links
- Detecting delivery zones
- Visualizing assignments on a map

---

## 🧠 Key Features

- 📍 **Location-based rider assignment** using Google Maps Distance Matrix API
- ⏱️ **Food preparation time** calculation from Excel-based item list
- 🛵 **Rider selection** based on proximity and availability
- 🗺️ **Polygon-based delivery zone validation**
- 📌 **Database-driven** operations with MySQL
- 🖼️ **Folium map** output for visual inspection of assignments
- ✅ Automatic assignment of both normal and subscription orders
- 🗺️ Zone detection using polygon mapping
- 🛵 Finds nearest available rider using Google Maps Distance Matrix API
- 📍 Google Maps link for optimized route
- 🔔 Rider and customer notification simulation
- 🗺️ Map output with assigned order pins (`order_assignment_map.html`)
- 🌐 Flask-based API with `/assign_orders` endpoint

---

## 🧰 Tech Stack

- **Python 3.x**
- **Flask** – lightweight API server
- **Google Maps API** – geocoding & distance estimation
- **MySQL** – storage for orders, riders, zones, and notifications
- **Folium** – interactive map generation
- **Pandas** – Excel reading & manipulation
- **Shapely** – polygon boundary validation
- **dotenv** – secure environment configuration


