import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression

# ---------------- CONFIG ----------------
WAQI_TOKEN = "176165c0a8c431b3c5fe786ad9286ed5be4e652f"
REFRESH_SECONDS = 600
HISTORY_FILE = "aqi_history.csv"

# ---------------- SELF-CLEAN CORRUPTED CSV ----------------
if os.path.exists(HISTORY_FILE):
    try:
        pd.read_csv(HISTORY_FILE)
    except:
        os.remove(HISTORY_FILE)

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
    try:
        r = requests.get(url, timeout=10).json()
    except:
        return None
    if r.get("status") != "ok":
        return None
    d = r["data"]
    return d.get("aqi"), d.get("city", {}).get("name")

# ---------------- AQI CATEGORY ----------------
def aqi_category(aqi):
    if aqi <= 50: return "Good", "🟢", "green"
    elif aqi <= 100: return "Satisfactory", "🟡", "lightgreen"
    elif aqi <= 200: return "Moderate", "🟠", "orange"
    elif aqi <= 300: return "Poor", "🔴", "red"
    elif aqi <= 400: return "Very Poor", "🟣", "darkred"
    else: return "Severe", "☠️", "black"

# ---------------- HEALTH ADVICE ----------------
def advice_block(aqi, persona):
    cat, icon, color = aqi_category(aqi)

    base = {
        "Good": "Air quality is safe for outdoor activities.",
        "Satisfactory": "Minor discomfort possible for sensitive people.",
        "Moderate": "Long outdoor exposure may cause breathing discomfort.",
        "Poor": "Unhealthy air. Limit outdoor exposure.",
        "Very Poor": "Serious health risk. Stay indoors.",
        "Severe": "Health emergency conditions."
    }

    reason = {
        "Good": "Pollutants are well below harmful limits.",
        "Satisfactory": "Pollution slightly elevated.",
        "Moderate": "PM2.5 may irritate airways.",
        "Poor": "High PM2.5 affects lungs and heart.",
        "Very Poor": "Prolonged exposure can cause respiratory damage.",
        "Severe": "Extremely high pollution levels."
    }

    advice = base[cat]
    why = reason[cat]

    if persona == "Children / Elderly" and aqi > 100:
        advice += " Children and elderly are at higher risk."
        why += " Lower immunity and lung strength."

    if persona == "Outdoor Workers" and aqi > 150:
        advice += " Use N95 masks and take frequent breaks."
        why += " Continuous inhalation increases exposure."

    return f"{icon} {advice}", f"Why: {why}", color

# ---------------- SAVE HISTORY ----------------
def save_history(area, aqi):
    now = datetime.now()
    new = pd.DataFrame([[now, area, aqi]], columns=["time", "area", "aqi"])

    if os.path.exists(HISTORY_FILE):
        try:
            df = pd.read_csv(HISTORY_FILE)
        except:
            df = pd.DataFrame(columns=["time", "area", "aqi"])
        df = pd.concat([df, new], ignore_index=True)
    else:
        df = new

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])
    df = df[df["time"] > (now - timedelta(hours=12))]
    df.to_csv(HISTORY_FILE, index=False)

# ---------------- ML FORECAST ----------------
def ai_forecast(area, current_aqi):
    if not os.path.exists(HISTORY_FILE):
        return current_aqi

    try:
        df = pd.read_csv(HISTORY_FILE)
    except:
        return current_aqi

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna()
    df = df[df["area"] == area]

    if len(df) < 5:
        return current_aqi

    df = df.sort_values("time").tail(12)

    now = df["time"].max()
    df["hours_from_now"] = (df["time"] - now).dt.total_seconds() / 3600

    X = df[["hours_from_now"]].values
    y = df["aqi"].values

    model = LinearRegression()
    model.fit(X, y)

    prediction = model.predict(np.array([[6]]))[0]
    return int(max(0, min(500, prediction)))

# ---------------- UI ----------------
st.set_page_config(page_title="AeroGuard – ML AQI Forecast", layout="wide")
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>", unsafe_allow_html=True)

st.title("🌬️ AeroGuard – Hyperlocal AQI & ML Forecast (Next 6 Hours)")

persona = st.selectbox(
    "Select User Category",
    ["General Public", "Children / Elderly", "Outdoor Workers"]
)

rows, colors = [], []

for loc, (lat, lon) in locations.items():
    res = fetch_waqi(lat, lon)
    if not res:
        continue

    aqi, station = res
    save_history(loc, aqi)
    forecast = ai_forecast(loc, aqi)

    cat, icon, _ = aqi_category(aqi)
    advice, why, color = advice_block(aqi, persona)

    rows.append([loc, station, aqi, f"{icon} {cat}", forecast, advice, why])
    colors.append(color)

df = pd.DataFrame(rows, columns=[
    "Area", "Nearest Station", "AQI Now",
    "Category", "AQI (6h Forecast)",
    "Health Advice", "Why this advice?"
])

st.subheader("📊 Live AQI & Health Guidance")
st.data_editor(df, use_container_width=True, hide_index=True, disabled=True)

# ---------------- GRAPH ----------------
st.subheader("📈 ML-Based AQI Forecast")
area_sel = st.selectbox("Select Area", df["Area"])
now_val = df[df["Area"] == area_sel]["AQI Now"].values[0]
fut_val = df[df["Area"] == area_sel]["AQI (6h Forecast)"].values[0]

fig, ax = plt.subplots()
ax.plot([0, 6], [now_val, fut_val], marker="o")
ax.set_xlabel("Hours Ahead")
ax.set_ylabel("AQI")
ax.set_title(f"AQI Forecast – {area_sel}")
st.pyplot(fig)

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
        popup=f"<b>{r['Area']}</b><br>AQI: {r['AQI Now']}<br>6h Forecast: {r['AQI (6h Forecast)']}"
    ).add_to(m)

st_folium(m, width=1100, height=500)

st.caption("Forecast generated using ML regression on recent AQI trends.")