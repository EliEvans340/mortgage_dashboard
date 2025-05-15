import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
from fredapi import Fred
import yfinance as yf

# Add your FRED API key (free at https://fred.stlouisfed.org/)
fred = Fred(api_key="e77ffd5020e10fd3410f3b13d83b5b68")

# Replace with your actual API key from https://api.census.gov/data/key_signup.html
CENSUS_API_KEY = 'e88c1f7dde0475245ac483559fa83aad443967f6'
CENSUS_base_url = 'https://api.census.gov/data/2021/acs/acs5'


@st.cache_data(ttl=3600)  # Refresh every hour


def get_30yr_mortgage_rate():
    try:
        rate = fred.get_series('MORTGAGE30US')[-1]
        return round(rate, 2)
    except Exception as e:
        st.warning(f"⚠️ Error fetching mortgage rate from FRED: {e}")
        return None

def get_live_rates():
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="1d")

        if hist.empty or "Close" not in hist:
            st.warning("⚠️ Yahoo Finance returned no data for ^TNX.")
            return None, None

        treasury_yield = hist["Close"].iloc[-1] 

    except Exception as e:
        st.warning(f"⚠️ Error fetching 10Y Treasury yield: {e}")
        treasury_yield = None

    try:
        mortgage_rate = get_30yr_mortgage_rate()
        if mortgage_rate is None:
            st.warning("⚠️ FRED API failed to return a mortgage rate.")
    except Exception as e:
        st.warning(f"⚠️ Error fetching mortgage rate: {e}")
        mortgage_rate = None

    return treasury_yield, mortgage_rate
    
# Load the data
@st.cache_data
def load_data():
    df = pd.read_csv("Mortgage_Rate_Indicators_Forecast.csv", parse_dates=['Date'])
    return df

data = load_data()

st.title("Mortgage Rate Indicators Dashboard")

# Date filter
date_range = st.slider(
    "Select date range:",
    min_value=data['Date'].min().to_pydatetime(),
    max_value=data['Date'].max().to_pydatetime(),
    value=(data['Date'].min().to_pydatetime(), data['Date'].max().to_pydatetime())
)

filtered_data = data[
    (data['Date'] >= pd.to_datetime(date_range[0])) & 
    (data['Date'] <= pd.to_datetime(date_range[1]))
]

# Indicator selection
indicator = st.selectbox("Select indicator to visualize:", data.columns.drop("Date"))

# Plot
fig = px.line(filtered_data, x="Date", y=indicator, title=f"{indicator} Over Time")
st.plotly_chart(fig)

# Correlation heatmap
if st.checkbox("Show Correlation Heatmap"):
    heatmap_data = data.drop(columns=["Date"]).corr()
    st.dataframe(heatmap_data.style.background_gradient(cmap='RdYlGn', axis=None))

import io

# --- Chart Download as PNG ---
try:
    import kaleido
    fig_bytes = io.BytesIO()
    fig.write_image(fig_bytes, format="png")

    st.download_button(
        label="📥 Download Chart as PNG",
        data=fig_bytes.getvalue(),
        file_name=f"{indicator}_chart.png",
        mime="image/png"
    )
except Exception as e:
    st.warning("⚠️ Install 'kaleido' to enable chart download: pip install kaleido")

# --- Excel Export of Filtered Data ---
csv_data = filtered_data.to_csv(index=False).encode('utf-8')

st.download_button(
    label="📊 Download Filtered Data (CSV)",
    data=csv_data,
    file_name="filtered_mortgage_data.csv",
    mime="text/csv"
)

# --- Forecast Alert Message ---
try:
    last_yield = data[data['Date'] == data['Date'].max()]['10Y_Treasury_Yield'].values[0]
    if last_yield > 5.0:
        st.warning("⚠️ 10Y Yield is projected above 5%. Mortgage rates may rise — refinancing could become less favorable.")
    elif last_yield < 3.5:
        st.success("✅ 10Y Yield is projected below 3.5%. Mortgage rates may drop — consider locking in refinancing.")
    else:
        st.info("ℹ️ Mortgage rates are expected to remain stable in the near term.")
except:
    st.info("ℹ️ Forecast alerts will appear here once 10Y Treasury Yield is loaded.")

try:
    forecast_window = filtered_data.copy()
    forecasted_yield = forecast_window['10Y_Treasury_Yield'].iloc[-1]

    # Real-world current rates (can later pull dynamically)
    actual_10Y_yield, actual_mortgage_rate = get_live_rates()
    #st.write(f"DEBUG - 10Y Yield: {actual_10Y_yield}, Mortgage Rate: {actual_mortgage_rate}")
    # Detailed debugging
    if actual_10Y_yield is None:
        st.error("⚠️ Failed to retrieve the 10-Year Treasury Yield from Yahoo Finance.")

    if actual_mortgage_rate is None:
        st.error("⚠️ Failed to retrieve the 30-Year Mortgage Rate from FRED API.")

    # Stop if either failed
    if actual_10Y_yield is None or actual_mortgage_rate is None:
        raise st.stop() 
    else:
        current_spread = round(actual_mortgage_rate - actual_10Y_yield, 2)

    st.subheader("📌 Investment Guidance")

    # Yield-based guidance
    if forecasted_yield > 5.0:
        st.error("📉 Forecasted 10Y Yield is above 5%.")
        st.write("Mortgage rates may increase. Consider delaying unless urgent.")
    elif forecasted_yield > 4.0:
        st.warning("📊 Forecasted 10Y Yield is between 4% and 5%.")
        st.write("Rates are stable. Lock only if timing matters.")
    else:
        st.success("✅ Forecasted 10Y Yield is below 4%.")
        st.write("Consider locking or refinancing now to capture lower rates.")

    # Spread-based risk analysis
    st.markdown("---")
    st.markdown(f"**📉 Current 10Y Treasury Yield**: {actual_10Y_yield:.2f}%  \n"
                f"**🏦 Current 30Y Mortgage Rate**: {actual_mortgage_rate:.2f}%  \n"
                f"**📊 Current Spread**: {current_spread:.2f}%")

    if current_spread > 2.0:
        st.warning("⚠️ Mortgage rates are elevated due to a higher-than-normal spread.\n\n"
                   "This suggests lenders are pricing in risk premiums — rates may come down even if Treasury yields stay flat.")
    else:
        st.success("✔️ Spread is within normal range. Mortgage pricing aligns with historical expectations.")

    st.caption(f"(Forecasted 10Y Yield: {forecasted_yield:.2f}%)")

except Exception as e:
    st.warning("⚠️ Could not generate investment guidance.")
    st.caption(str(e))

#US Census API Call
@st.cache_data(ttl=86400)
def get_city_labor_data():
    CENSUS_API_KEY = 'e88c1f7dde0475245ac483559fa83aad443967f6'
    CENSUS_base_url = 'https://api.census.gov/data/2021/acs/acs5'
    params = {
        'get': 'NAME,B01003_001E,B23025_005E',
        'for': 'place:*',
        'in': 'state:36',
        'key': CENSUS_API_KEY
    }

    response = requests.get(CENSUS_base_url, params=params)

    # 🛑 Stop and show error if request failed
    if response.status_code != 200:
        st.error(f"❌ Census API error: {response.status_code}")
        st.text(response.text[:1000])
        st.stop()

    # 🧪 Try to parse JSON or print the raw response
    try:
        data = response.json()
    except Exception as e:
        st.error("❌ Failed to parse Census response as JSON.")
        st.text(response.text[:1000])
        st.stop()

    # ✅ Normal logic continues
    df = pd.DataFrame(data[1:], columns=data[0])
    df['B01003_001E'] = pd.to_numeric(df['B01003_001E'], errors='coerce')
    df['B23025_005E'] = pd.to_numeric(df['B23025_005E'], errors='coerce')

    target_places = [
        "Oyster Bay", "Hempstead", "North Hempstead", "Islip",
        "Queens", "Brooklyn", "Staten Island"
    ]
    df_filtered = df[df['NAME'].str.lower().str.contains('|'.join([name.lower() for name in target_places]))].copy()

    df_filtered.rename(columns={
        'NAME': 'Place',
        'B01003_001E': 'Total_Population',
        'B23025_005E': 'Unemployed'
    }, inplace=True)

    df_filtered['Unemployment_Rate_%'] = (
        df_filtered['Unemployed'] / df_filtered['Total_Population'] * 100
    ).round(2)

    return df_filtered.reset_index(drop=True)

#BLS API Call
@st.cache_data(ttl=86400)
def get_bls_county_unemployment():
    BLS_API_KEY = "a8113b3e5ce94f11917a83b94e35e702"  # 🔐 Replace with your BLS key

    series_ids = {
        "Nassau County": "LAUCN360590000000003",
        "Suffolk County": "LAUCN361030000000003",
        "Queens County": "LAUCN360810000000003",
        "Kings County (Brooklyn)": "LAUCN360470000000003",
        "Richmond County (Staten Island)": "LAUCN360850000000003"
    }

    headers = {'Content-type': 'application/json'}
    data = {
        "seriesid": list(series_ids.values()),
        "startyear": "2024",
        "endyear": "2025",
        "registrationkey": BLS_API_KEY
    }

    response = requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/", json=data, headers=headers)

    # DEBUGGING BLOCK
    if response.status_code != 200:
        st.error(f"❌ BLS API Error: {response.status_code}")
        st.stop()

    results = response.json()

    if 'Results' not in results or 'series' not in results['Results']:
        st.error(f"❌ Unexpected BLS response: {results}")
        st.stop()

    # Continue only if structure is valid
    rows = []
    for i, series in enumerate(results['Results']['series']):
        county = list(series_ids.keys())[i]
        for entry in series['data']:
            if entry['period'].startswith("M"):  # Only monthly data
                rows.append({
                    "County": county,
                    "Year": entry['year'],
                    "Month": entry['periodName'],
                    "Unemployment Rate": float(entry['value'])
                })

    df = pd.DataFrame(rows)
    df['Date'] = pd.to_datetime(df['Month'] + " " + df['Year'], format="%B %Y")

    latest_month = df['Date'].max()
    latest_data = df[df['Date'] == latest_month].copy()

    return df, latest_data

# Pull both full and latest unemployment data
full_bls_data, latest_bls_data = get_bls_county_unemployment()

st.subheader("📍 Latest County-Level Unemployment Rates (BLS)")
st.dataframe(latest_bls_data[['County', 'Year', 'Month', 'Unemployment Rate']])

# Optional trend chart
if st.checkbox("📊 Show Monthly Unemployment Trends"):
    fig = px.line(full_bls_data.sort_values("Date"),
                  x="Date", y="Unemployment Rate", color="County",
                  title="Unemployment Trends by County (BLS Data)")
    st.plotly_chart(fig)

#US Census Table
st.header("🏙️ City/Town-Level Labor Market Data (Census)")

city_data = get_city_labor_data()

selected_place = st.selectbox("Select a Town or Borough", city_data['Place'])

selected_row = city_data[city_data['Place'] == selected_place].iloc[0]

st.metric("Total Population", f"{int(selected_row['Total_Population']):,}")
st.metric("Unemployed", f"{int(selected_row['Unemployed']):,}")
st.metric("Unemployment Rate", f"{selected_row['Unemployment_Rate_%']}%")

if st.checkbox("📄 Show full Census labor table"):
    st.dataframe(city_data)