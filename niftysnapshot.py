import requests, json
from datetime import datetime

def fetch_and_save_snapshot():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/option-chain"
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # required to get cookies

    res = session.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        now = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"nifty_snapshot_{now}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Snapshot saved as {filename}")
    else:
        print("❌ Failed to fetch data from NSE")

fetch_and_save_snapshot()
