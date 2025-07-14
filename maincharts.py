import requests
import json
from datetime import datetime

# --- Flask API Config ---
API_URL = "https://NSEOptionChainDashboard.up.railway.app/api/alert"

# --- Fetch Option Chain Data from Cached JSON ---
def load_cached_data(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load {filename}: {e}")
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

# --- Top Contributors by OI Change ---
def find_top_oi_contributors():
    current_data = load_cached_data("nifty_snapshot_2025-07-14_08-40.json")
    prev_data = load_cached_data("nifty_snapshot_2025-07-14_08-25.json")
    if not current_data or not prev_data:
        return

    expiry = current_data['records']['expiryDates'][0]
    current_records = {d['strikePrice']: d for d in current_data['records']['data'] if d['expiryDate'] == expiry}
    prev_records = {d['strikePrice']: d for d in prev_data['records']['data'] if d['expiryDate'] == expiry}

    contributors = []

    for strike in current_records:
        curr_ce = current_records[strike].get("CE", {})
        curr_pe = current_records[strike].get("PE", {})
        prev_ce = prev_records.get(strike, {}).get("CE", {})
        prev_pe = prev_records.get(strike, {}).get("PE", {})

        ce_oi_now = curr_ce.get("openInterest", 0)
        ce_oi_prev = prev_ce.get("openInterest", 0)
        pe_oi_now = curr_pe.get("openInterest", 0)
        pe_oi_prev = prev_pe.get("openInterest", 0)

        ce_vol = curr_ce.get("totalTradedVolume", 0)
        pe_vol = curr_pe.get("totalTradedVolume", 0)

        ce_oi_change = ce_oi_now - ce_oi_prev
        pe_oi_change = pe_oi_now - pe_oi_prev

        total_change = ce_oi_change + pe_oi_change

        contributors.append({
            "strike": strike,
            "CE_OI_Change": ce_oi_change,
            "PE_OI_Change": pe_oi_change,
            "Total_OI_Change": total_change,
            "CE_Volume": ce_vol,
            "PE_Volume": pe_vol
        })

    top10 = sorted(contributors, key=lambda x: x['Total_OI_Change'], reverse=True)[:10]

    for item in top10:
        trigger_alert(
            "Top OI Contributor",
            Strike=item['strike'],
            CE_OI_Change=item['CE_OI_Change'],
            PE_OI_Change=item['PE_OI_Change'],
            Total_OI_Change=item['Total_OI_Change'],
            CE_Volume=item['CE_Volume'],
            PE_Volume=item['PE_Volume']
        )

print("🔍 Finding top 10 OI contributors during 15-minute patch...")
find_top_oi_contributors()
