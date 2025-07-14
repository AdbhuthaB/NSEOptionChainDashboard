from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from datetime import datetime
import math
from collections import defaultdict
from scipy.stats import norm
import main
import maincharts
import os
port = int(os.environ.get("PORT", 5000))
app = Flask(__name__)
CORS(app)  # Allow requests from frontend

# In-memory alert store
alerts_list = []
def group_alerts_by_window(alerts, window_minutes=15):
    grouped = defaultdict(list)
    for alert in alerts:
        ts = datetime.fromisoformat(alert["timestamp"])
        window_start = ts.replace(minute=(ts.minute // window_minutes) * window_minutes, second=0, microsecond=0)
        grouped[window_start].append(alert)
    return grouped

def top_contributors_per_window(alerts, top_n=10):
    from collections import defaultdict
    from datetime import datetime

    def group_alerts_by_window(alerts, window_minutes=15):
        grouped = defaultdict(list)
        for alert in alerts:
            ts = datetime.fromisoformat(alert["timestamp"])
            window_start = ts.replace(minute=(ts.minute // window_minutes) * window_minutes, second=0, microsecond=0)
            grouped[window_start].append(alert)
        return grouped

    windowed = group_alerts_by_window(alerts)
    results = {}

    for window_start, alerts_in_window in windowed.items():
        contrib_scores = defaultdict(lambda: {"score": 0.0, "type": ""})

        for alert in alerts_in_window:
            details = alert.get("details", {})

            # Fallback to CE.underlying if symbol is missing
            symbol = alert.get("symbol")
            if not symbol:
                symbol = alert.get("underlying", "NIFTY")


            strike = details.get("Strike", "NA")
            alert_type = alert.get("type", "Unknown Alert")
            key = f"{symbol} {strike}"

            if "CE_Actual" in details and "CE_Theoretical" in details:
                score = abs(details["CE_Actual"] - details["CE_Theoretical"])
            elif "PE_Actual" in details and "PE_Theoretical" in details:
                score = abs(details["PE_Actual"] - details["PE_Theoretical"])
            elif "Premium" in details:
                score = details["Premium"]
            else:
                score = 1  # fallback

            contrib_scores[key]["score"] += score
            contrib_scores[key]["type"] = alert_type

        top_list = sorted(contrib_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:top_n]
        results[window_start.isoformat()] = [
            {"entity": entity, "score": round(data["score"], 2), "type": data["type"]}
            for entity, data in top_list
        ]

    return results
@app.route("/api/top-entities")
def get_top_entities():
    

    result = top_contributors_per_window(alerts_list, top_n=10)
    return jsonify(result)
def black_scholes_price(S, K, T, r, sigma, option_type='call'):
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'call':
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

@app.route("/api/theoretical-diff")
def theoretical_diff():
    # Load today's snapshot
    with open("nifty_snapshot_2025-07-14_12-24.json") as f:
        data = json.load(f)

    spot_price = data.get("records", {}).get("underlyingValue", 23000)  # fallback
    expiry = data["records"]["data"][0]["expiryDate"]
    expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
    today = datetime(2025, 7, 14)
    T = max((expiry_date - today).days / 365, 1/365)  # avoid 0
    r = 0.06  # risk-free rate

    ce_diff = []
    pe_diff = []

    for item in data["records"]["data"]:
        strike = item["strikePrice"]

        # CE
        if "CE" in item and item["CE"].get("lastPrice") and item["CE"].get("impliedVolatility"):
            market = item["CE"]["lastPrice"]
            sigma = item["CE"]["impliedVolatility"] / 100
            theo = black_scholes_price(spot_price, strike, T, r, sigma, 'call')
            ce_diff.append({"strike": strike, "diff": round(theo - market, 2)})

        # PE
        if "PE" in item and item["PE"].get("lastPrice") and item["PE"].get("impliedVolatility"):
            market = item["PE"]["lastPrice"]
            sigma = item["PE"]["impliedVolatility"] / 100
            theo = black_scholes_price(spot_price, strike, T, r, sigma, 'put')
            pe_diff.append({"strike": strike, "diff": round(theo - market, 2)})

    return jsonify({
        "ce": ce_diff,
        "pe": pe_diff
    })
@app.route("/api/top-diff-contributors")
def top_diff_contributors():
    with open("nifty_snapshot_2025-07-14_12-24.json") as f:
        data = json.load(f)

    spot_price = data.get("records", {}).get("underlyingValue", 23000)
    expiry = data["records"]["data"][0]["expiryDate"]
    expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
    today = datetime(2025, 7, 14)
    T = max((expiry_date - today).days / 365, 1/365)
    r = 0.06

    ce_diff = []
    pe_diff = []

    for item in data["records"]["data"]:
        strike = item["strikePrice"]

        if "CE" in item and item["CE"].get("lastPrice") and item["CE"].get("impliedVolatility"):
            market = item["CE"]["lastPrice"]
            sigma = item["CE"]["impliedVolatility"] / 100
            theo = black_scholes_price(spot_price, strike, T, r, sigma, 'call')
            diff = round(theo - market, 2)
            ce_diff.append({"strike": strike, "diff": diff, "abs_diff": abs(diff), "type": "CE"})

        if "PE" in item and item["PE"].get("lastPrice") and item["PE"].get("impliedVolatility"):
            market = item["PE"]["lastPrice"]
            sigma = item["PE"]["impliedVolatility"] / 100
            theo = black_scholes_price(spot_price, strike, T, r, sigma, 'put')
            diff = round(theo - market, 2)
            pe_diff.append({"strike": strike, "diff": diff, "abs_diff": abs(diff), "type": "PE"})

    # Combine and sort by absolute difference
    all_diff = ce_diff + pe_diff
    top10 = sorted(all_diff, key=lambda x: x["abs_diff"], reverse=True)[:10]

    return jsonify(top10)

@app.route('/api/alert', methods=['POST'])
def receive_alert():
    data = request.get_json()
    if data:
        alerts_list.append(data)
        print(f"[RECEIVED] {data}")
    return jsonify({"status": "received"}), 200

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
   for alert in alerts_list:
        details = alert.get("details", {})
        underlying = (
            alert.get("symbol") or
            details.get("ce_underlying") or
            details.get("pe_underlying") or
            details.get("underlying") or
            "UNKNOWN"
        )
        alert["underlying"] = underlying
        return jsonify(alerts_list), 200

if __name__ == '__main__':

    
    app.run()
