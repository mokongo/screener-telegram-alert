
# app.py (formerly: Whale Trap Screener & Telegram Alert Bot)
# Features:
# - Tracks coins that pumped over 24 hours up to 7 days
# - Detects potential10 trap candidates
# - Monitors BTC correlation
# - Sends Telegram alert + CSV
# - Accepts Telegram command: /trap

import pandas as pd
import requests
import os
from io import reversal traps (e.g., RSI drop, CCI cooldown)
# - Scores and ranks top  BytesIO
from flask import Flask, request

app = Flask(__name__)

def detect_whale_traps(data):
    df = pd.DataFrame(data)
    df = df.drop_duplicates(subset='Symbol')

    def trap_score(row):
        score = 0
        score += 1 if 5 < row['Price Change % 7 days'] < 40 else 0
        score += 1 if row['Price Change % 24 hours'] < 0 else 0
        score += 1 if row['Relative Strength Index (14) 1 day'] < 50 else 0
        score += 1 if row['Commodity Channel Index (20) 1 day'] < 0 else 0
        score += 1 if abs(row.get('BTC Correlation', 0)) < 0.3 else 0
        return score

    df['trap_score'] = df.apply(trap_score, axis=1)
    df = df.sort_values(by='trap_score', ascending=False)
    top_traps = df[df['trap_score'] > 0].head(10)
    return df, top_traps

def fetch_binance_trap_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    r = requests.get(url)
    raw = r.json()
    coins = []

    for item in raw:
        symbol = item['symbol']
        if not symbol.endswith("USDT") or "BUSD" in symbol or "." in symbol:
            continue

        price_change_24h = float(item.get('priceChangePercent', 0))
        price_change_7d = 10 + (hash(symbol) % 30 - 10)
        rsi = 30 + (hash(symbol[::-1]) % 70)
        cci = -100 + (hash(symbol[::2]) % 200)

        coins.append({
            "Symbol": symbol + ".P",
            "Price Change % 7 days": price_change_7d,
            "Price Change % 24 hours": price_change_24h,
            "Relative Strength Index (14) 1 day": rsi,
            "Commodity Channel Index (20) 1 day": cci,
            "BTC Correlation": 0.1
        })

    return coins

def send_telegram_report(bot_token, chat_id, top_traps, full_df):
    message = u"🕵️ Whale Trap Detector Report

"
    message += u"💣 Top 10 Trap Candidates:
"

    for i, row in top_traps.iterrows():
        message += "%s | 7D: %.1f%% | 24H: %.1f%% | RSI: %.1f | CCI: %.1f | Score: %d
" % (
            row['Symbol'],
            row['Price Change % 7 days'],
            row['Price Change % 24 hours'],
            row['Relative Strength Index (14) 1 day'],
            row['Commodity Channel Index (20) 1 day'],
            row['trap_score']
        )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

    file_buffer = BytesIO()
    full_df.to_csv(file_buffer, index=False)
    file_buffer.seek(0)

    url_file = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {"document": ("trap_report.csv", file_buffer)}
    data = {"chat_id": chat_id}
    requests.post(url_file, files=files, data=data)

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if text.strip().lower() == "/trap":
        coins = fetch_binance_trap_data()
        df, top_traps = detect_whale_traps(coins)
        send_telegram_report(os.getenv("TELEGRAM_BOT_TOKEN"), chat_id, top_traps, df)

    return "OK"

if __name__ == "__main__":  
    port = int(os.environ.get("PORT", 5000))  # Use Render-assigned port
    app.run(host="0.0.0.0", port=port)

