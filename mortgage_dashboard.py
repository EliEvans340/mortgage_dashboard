import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from bs4 import BeautifulSoup

import yfinance as yf

@st.cache_data(ttl=3600)  # Refresh every hour
def get_30yr_mortgage_rate():
    url = "https://www.mortgagenewsdaily.com/mortgage-rates/30-year-fixed"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        page = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(page.content, "html.parser")

        rate_div = soup.find("div", class_="value")
        if not rate_div:
            st.warning("⚠️ Could not find mortgage rate div on Mortgage News Daily")
            return None

        rate_text = rate_div.text.strip().replace("%", "")
        return float(rate_text)
    except Exception as e:
        st.warning(f"⚠️ Error fetching mortgage rate from MND: {e}")
        return None

def get_live_rates():
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="1d")

        if hist.empty or "Close" not in hist:
            st.warning("⚠️ Yahoo Finance returned no data for ^TNX.")
            return None, None

        treasury_yield = hist["Close"].iloc[-1] / 100

    except Exception as e:
        st.warning(f"⚠️ Error fetching 10Y Treasury yield: {e}")
        treasury_yield = None

    try:
        mortgage_rate = get_30yr_mortgage_rate()
        if mortgage_rate is None:
            st.warning("⚠️ NerdWallet scrape failed to return a mortgage rate.")
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
    st.write(f"DEBUG - 10Y Yield: {actual_10Y_yield}, Mortgage Rate: {actual_mortgage_rate}")
    # Detailed debugging
    if actual_10Y_yield is None:
        st.error("⚠️ Failed to retrieve the 10-Year Treasury Yield from Yahoo Finance.")

    if actual_mortgage_rate is None:
        st.error("⚠️ Failed to retrieve the 30-Year Mortgage Rate from NerdWallet.")

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
    
