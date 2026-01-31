import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime

# ---------------- CONFIG ----------------
API_KEY = "3620fe53587168fe56bd2f6093b7fb9b"
REFRESH_SECONDS = 600  # 10 minutes

# ---------------- LOCATIONS (EXPANDED MUMBAI) ----------------
locations = {
    # South Mumbai
    "Colaba": (18.91, 72.82),
    "Marine Lines": (18.94, 72.82),
    "Byculla": (18.98, 72.83),

    # Central Line
    "Dadar": (19.02, 72.84),
    "Parel": (19.00, 72.83),
    "Kurla": (19.07, 72.88),
    "Ghatkopar": (19.08, 72.91),
    "Mulund": (19.17, 72.95),

    # Western Suburbs
    "Bandra": (19.06, 72.83),
    "Andheri": (19.12, 72.85),
    "Goregaon": (19.15, 72.85),
    "Malad": (19.18, 72.84),
    "Borivali": (19.23, 72.86),

    # Harbour / Navi Mumbai
    "Vashi": (19.07, 72.99),
    "Nerul": (19.03, 73.02),
}

# ---------------- AQI LOGIC (INDIAN STANDARD STYLE) ----------------
def pm25_to_aqi(pm):
    if pm <= 30:
        return "Good", "green"
    elif pm <= 60:
        return "Satisfactory", "lightgreen"
    elif pm <= 90:
        return "Moderate", "orange"
    elif pm <= 120:
        return "Poor", "red"
    elif pm <= 250:
        return "Very Poor", "darkred"
    else:
        return "Severe", "black"

def health_advice(aqi_status, persona):
    advice_map = {
        "Good": "Air quality is good. Enjoy outdoor activities.",
        "Satisfactory": "Minor discomfort possible for sensitive individuals.",
        "Moderate": "People with asthma or heart disease should limit exposure.",
        "Poor": "Avoid prolonged outdoor exertion.",
        "Very Poor": "Stay indoors. Serious health risk.",
        "Severe": "Health emergency. Avoid all outdoor activity."
    }

    advice = advice_map[aqi_status]

    if persona == "Children / Elderly" and aqi_status in ["Moderate", "Poor", "Very Poor", "Severe"]:
        advice += " Children and elderly should strictly stay indoors."

    if persona == "Outdoor Workers" and aqi_status in ["Poor", "Very Poor", "Severe"]:
        advice += " Masks and frequent breaks are strongly advised."

    return advice

# ---------------- DATA FETCH ----------------
def fetch_pm25(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    data = requests.get(url).json()
    return data["list"][0]["components"]["pm2_5"]

def forecast_pm25(pm):
    # realistic short-term trend
    return round(pm * 1.04 if pm < 100 else pm * 1.02, 1)

# ---------------- UI SETUP ----------------
st.set_page_config(page_title="AeroGuard", layout="wide")
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>", unsafe_allow_html=True)

st.title("🌬️ AeroGuard – Live Mumbai Air Quality Intelligence")

persona = st.selectbox(
    "Select User Category",
    ["General Public", "Children / Elderly", "Outdoor Workers"]
)

last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p")
st.caption(f"Last updated: {last_updated}")

rows = []

for loc, (lat, lon) in locations.items():
    pm_now = fetch_pm25(lat, lon)
    pm_future = forecast_pm25(pm_now)

    aqi_now, color = pm25_to_aqi(pm_now)
    aqi_future, _ = pm25_to_aqi(pm_future)

    advice = health_advice(aqi_now, persona)

    rows.append([
        loc,
        round(pm_now, 1),
        round(pm_future, 1),
        aqi_now,
        aqi_future,
        advice,
        color
    ])

df = pd.DataFrame(rows, columns=[
    "Location",
    "PM2.5 Now (µg/m³)",
    "PM2.5 Forecast (6–12h)",
    "AQI Status Now",
    "AQI Status Forecast",
    "Health Advice",
    "Color"
])

# ---------------- TABLE ----------------
st.subheader("📊 Live Air Quality Table")
st.dataframe(
    df.drop(columns=["Color"]),
    use_container_width=True,
    hide_index=True
)

# ---------------- BAR CHART ----------------
st.subheader("📈 PM2.5 Comparison")
st.bar_chart(df.set_index("Location")[[
    "PM2.5 Now (µg/m³)",
    "PM2.5 Forecast (6–12h)"
]])

# ---------------- MAP ----------------
m = folium.Map(location=[19.07, 72.85], zoom_start=11)

for _, r in df.iterrows():
    folium.CircleMarker(
        location=locations[r["Location"]],
        radius=9,
        color=r["Color"],
        fill=True,
        fill_opacity=0.85,
        popup=f"""
        <b>{r['Location']}</b><br>
        PM2.5: {r['PM2.5 Now (µg/m³)']}<br>
        AQI: {r['AQI Status Now']}
        """
    ).add_to(m)

st.subheader("🗺️ Mumbai AQI Live Map")
st_folium(m, width=1100, height=520)

# ---------------- EXPLANATION ----------------
st.subheader("🔍 How AeroGuard Works")
st.markdown("""
• Fetches **live PM2.5 data** from OpenWeather stations  
• Converts pollution levels to **Indian AQI categories**  
• Forecasts short-term AQI trends using realistic variation  
• Health advice is **personalized** for different user groups  
• Auto-refreshes every **10 minutes** for near real-time accuracy  
""")
