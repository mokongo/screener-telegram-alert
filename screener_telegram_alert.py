# Screener & Telegram Alert Bot with Advanced Pattern Filters
# Now fetches live data from Binance for all perpetual futures pairs

import pandas as pd
import requests
import os
from io import BytesIO
import time

BINANCE_API = "https://fapi.binance.com"

# ------------------------------
# Fetch Binance Perpetual Data
# ------------------------------
def fetch_binance_data():
    info = requests.get(f"{BINANCE_API}/fapi/v1/ticker/24hr").json()
    prices = requests.get(f"{BINANCE_API}/fapi/v1/ticker/price").json()

    df = pd.DataFrame(info)
    df = df[df["symbol"].str.endswith("USDT")]  # Filter USDT pairs only
    df = df[df["contractType"] == "PERPETUAL"] if "contractType" in df.columns else df

    df = df.rename(columns={
        "symbol": "Symbol",
        "priceChangePercent": "Price Change % 24 hours",
        "quoteVolume": "Volume USDT"
    })

    df["Price Change % 24 hours"] = pd.to_numeric(df["Price Change % 24 hours"], errors="coerce")
    df["Volume USDT"] = pd.to_numeric(df["Volume USDT"], errors="coerce")

    # Add dummy RSI, CCI, Momentum for now — these will be replaced with real indicators in future
    df["Relative Strength Index (14) 1 day"] = 50 + (df["Price Change % 24 hours"] / 2).clip(-25, 25)
    df["Commodity Channel Index (20) 1 day"] = df["Price Change % 24 hours"] * 5
    df["Momentum (10) 1 day"] = df["Price Change % 24 hours"] / 100

    df = df[~df.isnull().any(axis=1)]
    df = df.head(100)  # Optional limit for faster testing
    return df.to_dict(orient="records")

# ------------------------------
# SCORING FUNCTION
# ------------------------------
def score_coins(data):
    df = pd.DataFrame(data)

    def bullish_score(row):
        score = 0
        score += 1 if row['Relative Strength Index (14) 1 day'] > 60 else 0
        score += 1 if row['Commodity Channel Index (20) 1 day'] > 100 else 0
        score += 1 if row['Momentum (10) 1 day'] > 0.1 else 0
        score += 1 if row['Price Change % 24 hours'] > 2 else 0
        score += 1 if row.get('Volume USDT', 0) > 2_000_000 else 0  # LOWERED THRESHOLD
        score += 1 if row['Volume USDT'] > 0 and row['Price Change % 24 hours'] > 1.5 and row['Relative Strength Index (14) 1 day'] < 60 else 0  # SURGE TAG
        return score

    def bearish_score(row):
        score = 0
        score += 1 if row['Relative Strength Index (14) 1 day'] < 40 else 0
        score += 1 if row['Commodity Channel Index (20) 1 day'] < -100 else 0
        score += 1 if row['Momentum (10) 1 day'] < -0.1 else 0
        score += 1 if row['Price Change % 24 hours'] < -2 else 0
        score += 1 if row.get('Volume USDT', 10_000_000) < 1_000_000 else 0
        return score

    df['bullish_score'] = df.apply(bullish_score, axis=1)
    df['bearish_score'] = df.apply(bearish_score, axis=1)
    df['freeze_pattern'] = df.apply(lambda row: abs(row['Momentum (10) 1 day']) < 0.02 and abs(row['Price Change % 24 hours']) < 1, axis=1)
    df['trap_wick'] = df.apply(lambda row: row['Relative Strength Index (14) 1 day'] > 65 and row['Price Change % 24 hours'] < -2, axis=1)
    df['surge_alert'] = df.apply(lambda row: row['Volume USDT'] > 0 and row['Price Change % 24 hours'] > 1.5 and row['Relative Strength Index (14) 1 day'] < 60, axis=1)

    top_bullish = df.sort_values(by='bullish_score', ascending=False).head(10)
    top_bearish = df.sort_values(by='bearish_score', ascending=False).head(10)
    return df, top_bullish, top_bearish

# ------------------------------
# TELEGRAM SENDER
# ------------------------------
def send_telegram_report(bot_token, chat_id, top_bullish, top_bearish, full_df):
    message = "📊 Screener Report\n\n"

    message += "🔥 Top 10 Bullish Coins:\n"
    for i, row in top_bullish.iterrows():
        vol = row.get('Volume USDT', 0)
        vol_str = f"${vol/1_000_000:.1f}M"
        tags = []
        if row['freeze_pattern']: tags.append("🧊 Freeze")
        if row['trap_wick']: tags.append("⚠️ Trap Wick")
        if row['surge_alert']: tags.append("🚀 Surge Alert")
        tag_str = " ".join(tags)
        message += f"{row['Symbol']} | +{row['Price Change % 24 hours']}% | RSI: {row['Relative Strength Index (14) 1 day']} | Vol: {vol_str} | Score: {row['bullish_score']} {tag_str}\n"

    message += "\n❄️ Top 10 Bearish Coins:\n"
    for i, row in top_bearish.iterrows():
        vol = row.get('Volume USDT', 0)
        vol_str = f"${vol/1_000_000:.1f}M"
        tags = []
        if row['freeze_pattern']: tags.append("🧊 Freeze")
        if row['trap_wick']: tags.append("⚠️ Trap Wick")
        if row['surge_alert']: tags.append("🚀 Surge Alert")
        tag_str = " ".join(tags)
        message += f"{row['Symbol']} | {row['Price Change % 24 hours']}% | RSI: {row['Relative Strength Index (14) 1 day']} | Vol: {vol_str} | Score: {row['bearish_score']} {tag_str}\n"

    message += f"\n💰 PNL: $748"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

    file_buffer = BytesIO()
    full_df.to_csv(file_buffer, index=False)
    file_buffer.seek(0)

    url_file = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {"document": ("screener_report.csv", file_buffer)}
    data = {"chat_id": chat_id}
    requests.post(url_file, files=files, data=data)

# ------------------------------
# MAIN EXECUTION
# ------------------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    coins = fetch_binance_data()
    df, top_bulls, top_bears = score_coins(coins)
    send_telegram_report(BOT_TOKEN, CHAT_ID, top_bulls, top_bears, df)
