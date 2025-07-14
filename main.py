import requests
import json
from datetime import datetime

# --- Flask API Config ---
API_URL = "https://NSEOptionChainDashboard.up.railway.app/api/alert"

# --- Fetch Option Chain Data from Cached JSON ---
def fetch_option_chain():
    try:
        with open("nifty_snapshot_2025-07-14_12-24.json", "r") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"❌ Failed to load cached option chain: {e}")
        return None

# --- Send Alert to Flask ---
def trigger_alert(alert_type, **kwargs):
    payload = {
        "type": alert_type,
        "timestamp": datetime.now().isoformat(),
        "details": kwargs
    }
    print(f"[ALERT] {alert_type} | {kwargs}")
    try:
        r = requests.post(API_URL, json=payload)
        r.raise_for_status()
        print("✅ Alert sent")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")

# --- Simple Theoretical Price Estimation (Black-Scholes Placeholder) ---
def estimate_theoretical_price(spot, strike):
    # For simplicity, assume a constant fair premium approximation
    return max(spot - strike, 0) + 20  # Intrinsic + dummy time value

# --- Run One-Time Analysis for ATM ±3 Strikes ---
def analyze_today_option_chain():
    data = fetch_option_chain()
    if not data:
        return

    records = data['records']
    underlying = records['underlyingValue']
    expiry = records['expiryDates'][0]
    strikes = records['strikePrices']
    atm_strike = min(strikes, key=lambda x: abs(x - underlying))

    # Collect data for ATM ±3 strikes
    range_strikes = [s for s in strikes if abs(s - atm_strike) <= 3 * 50]  # assuming 50-point steps
    filtered = [d for d in records['data'] if d['strikePrice'] in range_strikes and d['expiryDate'] == expiry]

    for opt in filtered:
        ce = opt.get('CE', {})
        pe = opt.get('PE', {})
        strike = opt['strikePrice']

        ce_oi = ce.get('openInterest')
        pe_oi = pe.get('openInterest')
        ce_price = ce.get('lastPrice')
        pe_price = pe.get('lastPrice')
        ce_underlying = ce.get('underlying')
        pe_underlying = pe.get('underlying')
        # --- Rule 1: Compare with theoretical price ---
        if ce_price:
            ce_theoretical = estimate_theoretical_price(underlying, strike)
            if abs(ce_price - ce_theoretical) > 20:
                trigger_alert("CE Price Deviates from Theory", Strike=strike, CE_Actual=ce_price, ce_underlying=ce_underlying, CE_Theoretical=ce_theoretical)

        if pe_price:
            pe_theoretical = estimate_theoretical_price(strike, underlying)  # Reversed for PE
            if abs(pe_price - pe_theoretical) > 20:
                trigger_alert("PE Price Deviates from Theory", Strike=strike, PE_Actual=pe_price, pe_underlying=pe_underlying, PE_Theoretical=pe_theoretical)

        # --- Rule 2: High Straddle Premium ---
        if ce_price and pe_price:
            total_premium = ce_price + pe_price
            if total_premium > 250:
                trigger_alert("High Straddle Premium", Strike=strike, Premium=total_premium)

        # --- Rule 3: High OI ---
        if ce_oi and pe_oi:
            total_oi = ce_oi + pe_oi
            if total_oi > 800000:
                trigger_alert("High Open Interest", Strike=strike, TotalOI=total_oi)

print("🔍 Running analysis on today's option chain (ATM ± 3 strikes)...")
analyze_today_option_chain()
