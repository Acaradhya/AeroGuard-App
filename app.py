import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor
from streamlit_autorefresh import st_autorefresh

# ---------------- CONFIG ----------------
WAQI_TOKEN = "176165c0a8c431b3c5fe786ad9286ed5be4e652f"
REFRESH_SECONDS = 600  # Refresh interval in seconds
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

# ---------------- UI CONFIG ----------------
st.set_page_config(page_title="AeroGuard – AI AQI Forecast", layout="wide")
# Auto-refresh without page reload
count = st_autorefresh(interval=REFRESH_SECONDS * 1000, limit=None, key="live_refresh")

st.title("🌬️ AeroGuard – Hyperlocal AQI & AI Forecast (Next 6 Hours)")

persona = st.selectbox(
    "Select User Category",
    ["General Public", "Children / Elderly", "Outdoor Workers"]
)

# ---------------- WAQI FETCH (PARALLEL & CACHED) ----------------
@st.cache_data(ttl=REFRESH_SECONDS)
def fetch_waqi(lat, lon):
    try:
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_TOKEN}"
        r = requests.get(url, timeout=10).json()
        if r["status"] != "ok":
            return None
        d = r["data"]
        return d.get("aqi"), d.get("iaqi", {}).get("pm25", {}).get("v"), d.get("city", {}).get("name")
    except:
        return None

def fetch_all_locations(locations):
    results = {}
    with ThreadPoolExecutor(max_workers=len(locations)) as executor:
        future_to_loc = {executor.submit(fetch_waqi, lat, lon): loc for loc, (lat, lon) in locations.items()}
        for future in future_to_loc:
            loc = future_to_loc[future]
            res = future.result()
            if res:
                results[loc] = res
    return results

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
def save_history(data_rows):
    now = datetime.now()
    new = pd.DataFrame(data_rows, columns=["time", "area", "aqi"])
    if os.path.exists(HISTORY_FILE) and os.stat(HISTORY_FILE).st_size > 0:
        try:
            df = pd.read_csv(HISTORY_FILE)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=["time", "area", "aqi"])
        df = pd.concat([df, new], ignore_index=True)
    else:
        df = new
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["time"] > (now - timedelta(hours=12))]
    df.to_csv(HISTORY_FILE, index=False)
    return df

def ai_forecast(area, df_area, current_aqi):
    if len(df_area) < 4:
        return current_aqi
    recent = df_area.tail(6)["aqi"].values
    trend = (recent[-1] - recent[0]) / len(recent)
    return max(0, min(500, int(current_aqi + trend * 6)))

# ---------------- FETCH DATA ----------------
waqi_results = fetch_all_locations(locations)

data_rows = []
colors = []
rows = []

for loc, res in waqi_results.items():
    aqi, pm25, station = res
    data_rows.append([datetime.now(), loc, aqi])

# Save history once per run
history_df = save_history(data_rows)

for loc, res in waqi_results.items():
    aqi, pm25, station = res
    df_area = history_df[history_df["area"] == loc]
    forecast = ai_forecast(loc, df_area, aqi)
    
    cat, icon, _ = aqi_category(aqi)
    advice, why, color = advice_block(aqi, persona)

    rows.append([loc, station, aqi, f"{icon} {cat}", forecast, advice, why])
    colors.append(color)

df = pd.DataFrame(rows, columns=[
    "Area", "Nearest Station", "AQI Now", "Category",
    "AQI (6h Forecast)", "Health Advice", "Why this advice?"
])

# ---------------- TABLE ----------------
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

# ---------------- MAP WITH FORECAST TREND ----------------
st.subheader("🗺️ Mumbai AQI Map (Trend-Based Coloring)")
m = folium.Map(location=[19.07, 72.88], zoom_start=11)

for i, r in df.iterrows():
    # Determine color based on current AQI and forecast trend
    trend = r["AQI (6h Forecast)"] - r["AQI Now"]
    base_color = colors[i]
    if trend > 20:      # AQI rising sharply
        display_color = "darkred"
    elif trend > 0:     # AQI rising mildly
        display_color = "red"
    elif trend < -20:   # AQI dropping sharply
        display_color = "green"
    elif trend < 0:     # AQI dropping mildly
        display_color = "lightgreen"
    else:
        display_color = base_color  # No significant change

    folium.CircleMarker(
        location=locations[r["Area"]],
        radius=10,
        color=display_color,
        fill=True,
        fill_opacity=0.8,
        popup=f"""
        <b>{r['Area']}</b><br>
        AQI Now: {r['AQI Now']}<br>
        Forecast (6h): {r['AQI (6h Forecast)']}<br>
        Trend: {'⬆️' if trend>0 else '⬇️' if trend<0 else '➡️'} {trend:+}
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
