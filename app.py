import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime

# ---------------- CONFIG ----------------
WAQI_TOKEN = "176165c0a8c431b3c5fe786ad9286ed5be4e652f"
REFRESH_SECONDS = 600  # 10 minutes

# ---------------- LOCATIONS (Mumbai-wide) ----------------
locations = {
    "Colaba": (18.9067, 72.8147),
    "Worli": (19.0176, 72.8562),
    "Dadar": (19.0178, 72.8478),
    "Bandra": (19.0596, 72.8295),
    "Andheri": (19.1197, 72.8468),
    "Kurla": (19.0726, 72.8845),
    "Ghatkopar": (19.0856, 72.9081),
    "Chembur": (19.0623, 72.9005),
    "Powai": (19.1176, 72.9060),
    "Mulund": (19.1726, 72.9565),
    "Vashi": (19.0771, 72.9986),
}

# ---------------- FUNCTIONS ----------------
def fetch_waqi(lat, lon):
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_TOKEN}"
    r = requests.get(url, timeout=10).json()

    if r["status"] != "ok":
        return None

    data = r["data"]
    aqi = data.get("aqi", None)
    pm25 = data.get("iaqi", {}).get("pm25", {}).get("v", None)
    station = data.get("city", {}).get("name", "Unknown")
    time_str = data.get("time", {}).get("s", None)

    return aqi, pm25, station, time_str

def aqi_category(aqi):
    if aqi <= 50: return "Good"
    elif aqi <= 100: return "Satisfactory"
    elif aqi <= 200: return "Moderate"
    elif aqi <= 300: return "Poor"
    elif aqi <= 400: return "Very Poor"
    else: return "Severe"

def health_advice(aqi, persona):
    base = {
        "Good": "Safe for all outdoor activities.",
        "Satisfactory": "Minor discomfort possible for sensitive individuals.",
        "Moderate": "Avoid prolonged outdoor exertion.",
        "Poor": "Limit outdoor exposure. Masks recommended.",
        "Very Poor": "Avoid outdoor activity. Health effects likely.",
        "Severe": "Stay indoors. Serious health risk."
    }

    category = aqi_category(aqi)
    advice = base[category]

    if persona == "Children / Elderly" and aqi > 100:
        advice += " Extra caution advised for vulnerable groups."
    if persona == "Outdoor Workers" and aqi > 150:
        advice += " Use N95 masks and take frequent breaks."

    return category, advice

# ---------------- STREAMLIT CONFIG ----------------
st.set_page_config(page_title="AeroGuard – Mumbai AQI", layout="wide")
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>", unsafe_allow_html=True)

# ---------------- UI ----------------
st.title("🌬️ AeroGuard – Live Mumbai Air Quality (Sensor-Based)")

persona = st.selectbox(
    "Select User Category",
    ["General Public", "Children / Elderly", "Outdoor Workers"]
)

rows = []
last_updated_times = []

for loc, (lat, lon) in locations.items():
    result = fetch_waqi(lat, lon)
    if result is None:
        continue

    aqi, pm25, station, time_str = result
    category, advice = health_advice(aqi, persona)

    rows.append([
        loc,
        station,
        aqi,
        category,
        pm25,
        advice
    ])

    if time_str:
        last_updated_times.append(time_str)

df = pd.DataFrame(rows, columns=[
    "Area",
    "Nearest Station",
    "AQI",
    "Category",
    "PM2.5 (µg/m³)",
    "Health Advice"
])

st.subheader("📊 Live AQI Table (Real Sensor Data)")
st.dataframe(df, use_container_width=True)

# ---------------- MAP ----------------
m = folium.Map(location=[19.07, 72.88], zoom_start=11)

def aqi_color(aqi):
    if aqi <= 50: return "green"
    elif aqi <= 100: return "lightgreen"
    elif aqi <= 200: return "orange"
    elif aqi <= 300: return "red"
    elif aqi <= 400: return "darkred"
    else: return "black"

for _, r in df.iterrows():
    folium.CircleMarker(
        location=locations[r["Area"]],
        radius=10,
        color=aqi_color(r["AQI"]),
        fill=True,
        fill_opacity=0.8,
        popup=f"""
        <b>{r['Area']}</b><br>
        Station: {r['Nearest Station']}<br>
        AQI: {r['AQI']} ({r['Category']})<br>
        PM2.5: {r['PM2.5 (µg/m³)']}
        """
    ).add_to(m)

st.subheader("🗺️ Mumbai Live AQI Map")
st_folium(m, width=900, height=500)

# ---------------- FOOTER ----------------
if last_updated_times:
    latest_time = max(last_updated_times)
    st.caption(f"🕒 Last updated from CPCB/WAQI sensors at: {latest_time}")

st.subheader("ℹ️ How AeroGuard Works")
st.markdown("""
• Uses **WAQI (World Air Quality Index)** real-time sensor data  
• Data sourced from **CPCB & SAFAR monitoring stations**  
• No estimation or artificial AQI calculation  
• Personalized health guidance for different user groups  
• Auto-refreshes every 10 minutes  
""")
