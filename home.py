import webview
import requests
from datetime import datetime
import json
import time
import threading

# 1. THE FRONTEND (Same stable UI)
html_content = """
<!DOCTYPE html>
<html>
<head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #020617;
            --card-bg: #0f172a;
            --accent: #10b981;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.1);
        }
        body { background: var(--bg); color: var(--text-main); font-family: 'Inter', sans-serif; margin: 0; padding: 0; overflow: hidden; height: 100vh; }
        .header { -webkit-app-region: drag; height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 30px; background: rgba(0,0,0,0.2); }
        .exit-btn { -webkit-app-region: no-drag; background: #1e293b; border: 1px solid var(--border); color: var(--text-dim); width: 36px; height: 36px; border-radius: 10px; cursor: pointer; transition: all 0.2s; font-size: 16px; }
        .exit-btn:hover { background: #ef4444; color: white; border-color: #ef4444; }
        .container { display: grid; grid-template-columns: 340px 1fr; gap: 20px; padding: 20px 30px 30px 30px; height: calc(100vh - 90px); box-sizing: border-box; }
        .card { background: var(--card-bg); border-radius: 24px; padding: 25px; border: 1px solid var(--border); display: flex; flex-direction: column; position: relative; }
        h1 { margin: 5px 0; font-size: 70px; font-weight: 900; letter-spacing: -3px; color: var(--text-main); line-height: 1; }
        .stat-item { background: rgba(255,255,255,0.03); padding: 18px; border-radius: 18px; border: 1px solid var(--border); margin-top: 12px; display: flex; flex-direction: column; }
        .label { color: var(--text-dim); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px;}
        .val { font-size: 24px; font-weight: 800; display: block; margin-top: 2px; }
        .mwh-val { font-size: 11px; color: var(--text-dim); font-weight: 500; margin-top: 2px; }
        #priceChart { width: 100% !important; height: 100% !important; }
    </style>
</head>
<body>
    <div class="header">
        <span class="label" id="last-update">Price Analytics Pro // Connecting...</span>
        <button class="exit-btn" onclick="window.pywebview.api.close_window()">✕</button>
    </div>
    <div class="container">
        <div class="card">
            <div class="label" style="color: var(--accent);">● Current Rate (c/kWh)</div>
            <h1 id="price">--.--</h1>
            <div id="price-mwh" style="font-size: 14px; color: var(--text-dim); margin-bottom: 20px;">--.-- €/MWh</div>
            <div style="flex-grow: 1;"></div>
            <div class="stat-item"><div class="label">Minimum</div><span class="val" id="min-p" style="color: #34d399;">--</span><span class="mwh-val" id="min-mwh">--</span></div>
            <div class="stat-item"><div class="label">Average</div><span class="val" id="avg-p" style="color: #60a5fa;">--</span><span class="mwh-val" id="avg-mwh">--</span></div>
            <div class="stat-item"><div class="label">Maximum</div><span class="val" id="max-p" style="color: #f87171;">--</span><span class="mwh-val" id="max-mwh">--</span></div>
        </div>
        <div class="card">
            <div class="label" style="margin-bottom: 15px;">24h Market Trajectory (c/kWh)</div>
            <div style="flex-grow: 1; position: relative;"><canvas id="priceChart"></canvas></div>
        </div>
    </div>
    <script>
        let chart = null;
        function updateUI(data) {
            document.getElementById('price').innerText = data.current_price;
            document.getElementById('price-mwh').innerText = data.current_mwh + " €/MWh";
            document.getElementById('min-p').innerText = data.min_kwh + " c";
            document.getElementById('min-mwh').innerText = data.min_mwh + " €/MWh";
            document.getElementById('avg-p').innerText = data.avg_kwh + " c";
            document.getElementById('avg-mwh').innerText = data.avg_mwh + " €/MWh";
            document.getElementById('max-p').innerText = data.max_kwh + " c";
            document.getElementById('max-mwh').innerText = data.max_mwh + " €/MWh";
            document.getElementById('last-update').innerText = "Last Update: " + data.timestamp;

            const ctx = document.getElementById('priceChart').getContext('2d');
            if (chart) { chart.destroy(); }
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.prices.map(p => p.h + ":00"),
                    datasets: [{
                        data: data.prices.map(p => parseFloat(p.p)),
                        mwhData: data.prices.map(p => p.mwh_raw),
                        borderColor: '#10b981', borderWidth: 3, fill: true,
                        backgroundColor: 'rgba(16, 185, 129, 0.05)', tension: 0.3, pointRadius: 2
                    }]
                },
                options: {
                    animation: false, responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: {
                        callbacks: { label: function(c) { 
                            return [c.parsed.y.toFixed(2) + ' c/kWh', c.dataset.mwhData[c.dataIndex].toFixed(2) + ' €/MWh']; 
                        }}
                    }},
                    scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b' } } }
                }
            });
        }
    </script>
</body>
</html>
"""

# Backend
class API:
    def __init__(self, window): self._window = window
    def close_window(self): self._window.destroy()

    def get_data(self):
        vat, now = 1.24, datetime.now()
        try:
            url = f"https://dashboard.elering.ee/api/nps/price?start={now.strftime('%Y-%m-%dT00:00:00Z')}&end={now.strftime('%Y-%m-%dT23:59:59Z')}"
            e_res = requests.get(url).json()
            e_data = e_res['data']['ee']
            
            raw_mwh, prices, curr_kwh, curr_mwh = [], [], "--.--", "--.--"
            
            
            for item in e_data:
                dt = datetime.fromtimestamp(item['timestamp'])
                
                # Check if it's the top of the hour
                if dt.minute == 0:
                    mwh = item['price']
                    kwh = (mwh / 10) * vat
                    h = dt.hour
                    
                    raw_mwh.append(mwh)
                    prices.append({"h": f"{h:02}", "p": f"{kwh:.2f}", "mwh_raw": mwh})
                    
                    # Update current live price if hour matches
                    if h == now.hour:
                        curr_kwh, curr_mwh = f"{kwh:.2f}", f"{mwh:.2f}"

            # Calculate stats only if we have data
            if not raw_mwh: return None

            return {
                "current_price": curr_kwh, 
                "current_mwh": curr_mwh,
                "min_kwh": f"{(min(raw_mwh)/10)*vat:.2f}", 
                "min_mwh": f"{min(raw_mwh):.2f}",
                "avg_kwh": f"{(sum(raw_mwh)/len(raw_mwh)/10)*vat:.2f}", 
                "avg_mwh": f"{(sum(raw_mwh)/len(raw_mwh)):.2f}",
                "max_kwh": f"{(max(raw_mwh)/10)*vat:.2f}", 
                "max_mwh": f"{max(raw_mwh):.2f}",
                "prices": prices, 
                "timestamp": now.strftime("%H:%M:%S")
            }
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

def background_loop(window, api):
    #Refreshes the data every 15 minutes without closing the app.
    while True:
        data = api.get_data()
        if data:
            window.evaluate_js(f"updateUI({json.dumps(data)})")
        time.sleep(900) # 900 seconds = 15 minutes

def start_app(window):
    api = API(window)
    window.expose(api.close_window)
    # Start the update loop in a separate thread so it doesn't freeze the UI
    t = threading.Thread(target=background_loop, args=(window, api), daemon=True)
    t.start()

if __name__ == "__main__":
    window = webview.create_window('Electricty Marketprice', html=html_content, width=1100, height=750, frameless=True)
    webview.start(start_app, window)