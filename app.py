import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt

# ---------------- CONFIG ----------------
WAQI_TOKEN = "176165c0a8c431b3c5fe786ad9286ed5be4e652f"
REFRESH_SECONDS = 600
HISTORY_FILE = "aqi_history.csv"

# ---------------- LOCATIONS ----------------
locations = {
    "Colaba": (18.9067, 72.8147),
    "Worli": (19.0176, 72.8562),
    "Dadar": (19.0178, 72.8478),
    "Bandra": (19.0596, 72.8295),
    "Andheri": (19.1197, 72.8468),
    "Kurla": (19.0726, 72.8845),
    "Chembur": (19.0623, 72.9005),
    "Powai": (19.1176, 72.9060),
    "Mulund": (19.1726, 72.9565),
    "Vashi": (19.0771, 72.9986),
}

# ---------------- WAQI FETCH ----------------
def fetch_waqi(lat, lon):
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_TOKEN}"
    r = requests.get(url, timeout=10).json()
    if r["status"] != "ok":
        return None
    d = r["data"]
    return d.get("aqi"), d.get("iaqi", {}).get("pm25", {}).get("v"), d.get("city", {}).get("name")

# ---------------- AQI LOGIC ----------------
def aqi_category(aqi):
    if aqi <= 50: return "Good", "🟢", "green"
    elif aqi <= 100: return "Satisfactory", "🟡", "lightgreen"
    elif aqi <= 200: return "Moderate", "🟠", "orange"
    elif aqi <= 300: return "Poor", "🔴", "red"
    elif aqi <= 400: return "Very Poor", "🟣", "darkred"
    else: return "Severe", "☠️", "black"

def advice_block(aqi, persona):
    cat, icon, color = aqi_category(aqi)

    base = {
        "Good": "🌿 Air quality is clean and safe for outdoor activities.",
        "Satisfactory": "🙂 Minor discomfort possible for sensitive individuals.",
        "Moderate": "⚠️ Prolonged outdoor exertion may cause breathing discomfort.",
        "Poor": "😷 Air is unhealthy. Outdoor exposure should be limited.",
        "Very Poor": "🚨 Serious health risk. Stay indoors.",
        "Severe": "☠️ Health emergency. Avoid all outdoor exposure."
    }

    why = {
        "Good": "Pollutant levels are well below harmful thresholds.",
        "Satisfactory": "Pollution is slightly elevated but within acceptable limits.",
        "Moderate": "PM2.5 levels can irritate airways during long exposure.",
        "Poor": "High PM2.5 can aggravate asthma and heart conditions.",
        "Very Poor": "Sustained exposure may cause serious respiratory effects.",
        "Severe": "Extremely high pollution can trigger acute health emergencies."
    }

    advice = base[cat]
    reason = why[cat]

    if persona == "Children / Elderly" and aqi > 100:
        advice += " 👶👴 Children and elderly are at higher risk."
        reason += " Vulnerable lungs and immunity increase sensitivity."

    if persona == "Outdoor Workers" and aqi > 150:
        advice += " 🏭 Outdoor workers should wear N95 masks and take breaks."
        reason += " Continuous exposure increases inhaled pollutant dose."

    return f"{icon} {advice}", f"Why: {reason}", color

# ---------------- HISTORY & AI FORECAST ----------------
def save_history(area, aqi):
    now = datetime.now()
    new = pd.DataFrame([[now, area, aqi]], columns=["time", "area", "aqi"])
    if os.path.exists(HISTORY_FILE):
        df = pd.read_csv(HISTORY_FILE)
        df = pd.concat([df, new])
    else:
        df = new
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["time"] > (now - timedelta(hours=12))]
    df.to_csv(HISTORY_FILE, index=False)

def ai_forecast(area, current_aqi):
    if not os.path.exists(HISTORY_FILE):
        return current_aqi
    df = pd.read_csv(HISTORY_FILE)
    df = df[df["area"] == area]
    if len(df) < 4:
        return current_aqi
    recent = df.tail(6)["aqi"].values
    trend = (recent[-1] - recent[0]) / len(recent)
    return max(0, min(500, int(current_aqi + trend * 6)))

# ---------------- UI ----------------
st.set_page_config(page_title="AeroGuard – AI AQI Forecast", layout="wide")
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>", unsafe_allow_html=True)

st.title("🌬️ AeroGuard – Hyperlocal AQI & AI Forecast (Next 6 Hours)")

persona = st.selectbox(
    "Select User Category",
    ["General Public", "Children / Elderly", "Outdoor Workers"]
)

rows = []
colors = []

for loc, (lat, lon) in locations.items():
    res = fetch_waqi(lat, lon)
    if not res:
        continue

    aqi, pm25, station = res
    save_history(loc, aqi)
    forecast = ai_forecast(loc, aqi)

    cat, icon, _ = aqi_category(aqi)
    advice, why, color = advice_block(aqi, persona)

    rows.append([
        loc,
        station,
        aqi,
        f"{icon} {cat}",
        forecast,
        advice,
        why
    ])
    colors.append(color)

df = pd.DataFrame(rows, columns=[
    "Area",
    "Nearest Station",
    "AQI Now",
    "Category",
    "AQI (6h Forecast)",
    "Health Advice",
    "Why this advice?"
])

# ---------------- TABLE (WRAPPED TEXT) ----------------
st.subheader("📊 Live AQI, AI Forecast & Health Guidance")

st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Health Advice": st.column_config.TextColumn(width="large"),
        "Why this advice?": st.column_config.TextColumn(width="large")
    },
    disabled=True
)

# ---------------- FORECAST GRAPH ----------------
st.subheader("📈 AI-Based 6 Hour AQI Forecast")

area_sel = st.selectbox("Select Area", df["Area"])
now_val = df[df["Area"] == area_sel]["AQI Now"].values[0]
fut_val = df[df["Area"] == area_sel]["AQI (6h Forecast)"].values[0]

fig, ax = plt.subplots()
ax.plot([0, 6], [now_val, fut_val], marker="o")
ax.set_xlabel("Hours Ahead")
ax.set_ylabel("AQI")
ax.set_title(f"AQI Forecast Trend – {area_sel}")
st.pyplot(fig)

st.caption("Forecast generated using short-term time-series AI based on recent AQI trends.")

# ---------------- MAP ----------------
st.subheader("🗺️ Mumbai AQI Map")

m = folium.Map(location=[19.07, 72.88], zoom_start=11)

for i, r in df.iterrows():
    folium.CircleMarker(
        location=locations[r["Area"]],
        radius=9,
        color=colors[i],
        fill=True,
        fill_opacity=0.8,
        popup=f"""
        <b>{r['Area']}</b><br>
        AQI: {r['AQI Now']}<br>
        Forecast (6h): {r['AQI (6h Forecast)']}
        """
    ).add_to(m)

st_folium(m, width=1100, height=500)

# ---------------- EXPLANATION ----------------
st.subheader("ℹ️ How the AI Forecast Works")
st.markdown("""
• Uses **real CPCB / SAFAR sensor data** via WAQI  
• Maintains **rolling AQI history (last 6–12 hours)**  
• Applies **time-series trend analysis** for short-term forecasting  
• Predicts **AQI for the next 6 hours**  
• Advice is **personalized, explainable, and risk-aware**
""")