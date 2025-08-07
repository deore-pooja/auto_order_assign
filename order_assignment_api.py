import os
import time
import mysql.connector
import googlemaps
import folium
import pandas as pd
from flask import Flask, jsonify
from dotenv import load_dotenv
from shapely.geometry import Point, Polygon

# Load environment variables
load_dotenv()
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# Load Excel data for preparation times
prep_time_dict = {}
excel_path = 'Four-apps-food-item-List.xlsx'
prep_time_df = pd.read_excel(excel_path)
prep_time_df.columns = prep_time_df.columns.str.strip().str.replace('\xa0', ' ', regex=True)

required_cols = ['Time', 'Estimated Time(in min)']
if all(col in prep_time_df.columns for col in required_cols):
    prep_time_df.dropna(subset=required_cols, inplace=True)
    prep_time_df['Time'] = prep_time_df['Time'].astype(str).str.lower().str.strip()
    prep_time_dict = dict(zip(prep_time_df['Time'], prep_time_df['Estimated Time(in min)']))
else:
    print("Missing columns in Excel:", required_cols)

# Flask App setup
app = Flask(__name__)

# Database connection
def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        connect_timeout=60,
        connection_timeout=60
    )
    conn.ping(reconnect=True, attempts=3, delay=5)
    return conn

# Preparation time calculator
def get_preparation_time_summary(item_string):
    items = [i.strip().lower() for i in item_string.split(',')]
    total_time = 0
    details = []

    for item in items:
        time_needed = prep_time_dict.get(item)
        if time_needed is not None:
            total_time += time_needed
            details.append(f"{item.title()} ({time_needed} min)")
        else:
            details.append(f"{item.title()} (Not Found)")

    return total_time, details

# Geocoding helpers
def geocode_address(address):
    try:
        result = gmaps.geocode(address)
        if result:
            loc = result[0]['geometry']['location']
            return loc['lat'], loc['lng']
    except:
        pass
    return None, None

def get_distance_and_time(origin, destination):
    try:
        res = gmaps.distance_matrix([origin], [destination], mode="driving")
        if res['rows'][0]['elements'][0]['status'] == 'OK':
            d = res['rows'][0]['elements'][0]
            return d['distance']['text'], d['duration']['text']
    except Exception as e:
        print("Distance error:", e)
    return None, None

def get_direction_link(origin_lat, origin_lng, dest_lat, dest_lng):
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}&travelmode=driving"

# Load delivery zones
def load_zones():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, coordinates FROM zones WHERE status = 1")
    zones = []
    for row in cursor.fetchall():
        try:
            coords = [
                tuple(map(float, pt.replace("(", "").replace(")", "").strip().split(',')))
                for pt in row['coordinates'].split(',') if pt.count(',') == 1
            ]
            zones.append({'id': row['id'], 'title': row['title'], 'polygon': Polygon(coords)})
        except:
            continue
    cursor.close()
    conn.close()
    return zones

# DB Queries
def get_available_riders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tbl_rider WHERE status = 1")
    riders = cursor.fetchall()
    cursor.close()
    conn.close()
    return riders

def insert_rider_notifications(order_id, rider_ids, table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    for rid in rider_ids:
        cursor.execute("""
            INSERT INTO tbl_notification (uid, datetime, title, description, related_id, type)
            VALUES (%s, NOW(), %s, %s, %s, %s)
        """, (rid, "New Order Available", f"Please accept Order #{order_id}", order_id, table_name))
    conn.commit()
    cursor.close()
    conn.close()

def simulate_rider_acceptance(order_id, rider_ids):
    time.sleep(1)
    accepted = rider_ids[0]
    conn = get_db_connection()
    cursor = conn.cursor()
    for rid in rider_ids[1:]:
        cursor.execute("DELETE FROM tbl_notification WHERE uid = %s AND related_id = %s", (rid, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    return accepted

def assign_order(order_id, rider_id, table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE {table_name} SET rid = %s, order_status = 1 WHERE id = %s", (rider_id, order_id))
    cursor.execute("UPDATE tbl_rider SET rstatus = 1 WHERE id = %s", (rider_id,))
    conn.commit()
    cursor.close()
    conn.close()

def notify_user(uid, order_id, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tbl_notification (uid, datetime, title, description)
        VALUES (%s, NOW(), %s, %s)
    """, (uid, "Order Assigned!", f"{name}, your Order #{order_id} has been assigned."))
    conn.commit()
    cursor.close()
    conn.close()

def find_zone(lat, lng, zones):
    point = Point(lat, lng)
    for z in zones:
        if z['polygon'].contains(point):
            return z['id'], z['title']
    return None, None

# Order assignment logic
def process_order_table(table_name):
    zones = load_zones()
    riders = get_available_riders()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM {table_name} WHERE order_status = 0")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    order_map = folium.Map(location=[18.6, 73.75], zoom_start=12)
    assigned_orders = []
    assigned, not_assigned = 0, 0

    for order in orders:
        full_address = f"{order['address']}, {order['landmark']}"
        lat, lng = geocode_address(full_address)
        if not lat or not lng:
            print(f"Skipping Order #{order['id']} (Invalid address)")
            continue

        zone_id, zone_title = find_zone(lat, lng, zones)

        total_time, prep_details = 0, []
        if table_name == "tbl_normal_order" and 'items' in order:
            total_time, prep_details = get_preparation_time_summary(order['items'])
        elif table_name == "tbl_subscribe_order":
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT ptitle FROM tbl_subscribe_order_product WHERE oid = %s", (order['id'],))
            products = cursor.fetchall()
            cursor.close()
            conn.close()
            item_names = [p['ptitle'] for p in products]
            total_time, prep_details = get_preparation_time_summary(','.join(item_names))

        nearest_rider, best_dist, best_eta, best_link = None, None, None, None
        for r in riders:
            if r['rstatus'] == 0:
                r_lat, r_lng = float(r['lats']), float(r['longs'])
                dist, eta = get_distance_and_time((r_lat, r_lng), (lat, lng))
                if dist and (best_dist is None or float(dist.replace(' km', '').replace(',', '')) < float(best_dist.replace(' km', '').replace(',', ''))):
                    nearest_rider = r
                    best_dist, best_eta = dist, eta
                    best_link = get_direction_link(r_lat, r_lng, lat, lng)

        if nearest_rider:
            insert_rider_notifications(order['id'], [nearest_rider['id']], table_name)
            accepted_id = simulate_rider_acceptance(order['id'], [nearest_rider['id']])
            assign_order(order['id'], accepted_id, table_name)
            notify_user(order['uid'], order['id'], order['name'])

            folium.Marker(
                location=[lat, lng],
                popup=f"Order #{order['id']} → {nearest_rider['title']}\n{best_dist}, {best_eta}",
                icon=folium.Icon(color="green")
            ).add_to(order_map)

            order['assigned_rider_name'] = nearest_rider['title']
            order['zone'] = zone_title
            order['distance'] = best_dist
            order['eta'] = best_eta
            order['route_link'] = best_link
            assigned_orders.append(order)
            assigned += 1
        else:
            not_assigned += 1

    order_map.save("order_assignment_map.html")
    return assigned, not_assigned, assigned_orders

# -------------------- Flask Endpoints --------------------
@app.route('/')
def home():
    return jsonify({"message": "API is working!"})

@app.route('/assign_orders', methods=['GET'])
def assign_orders():
    try:
        a1, n1, list1 = process_order_table("tbl_normal_order")
        a2, n2, list2 = process_order_table("tbl_subscribe_order")

        detailed_assignments = []
        for order in list1 + list2:
            detailed_assignments.append({
                "order_id": order["id"],
                "user_name": order["name"],
                "zone": order.get("zone"),
                "assigned_rider": order.get("assigned_rider_name"),
                "distance": order.get("distance"),
                "eta": order.get("eta"),
                "google_maps_link": order.get("route_link")
            })

        return jsonify({
            "assigned": a1 + a2,
            "not_assigned": n1 + n2,
            "message": "Order assignment completed. Map saved as order_assignment_map.html",
            "details": detailed_assignments
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# -------------------- Run Locally or Render --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)


