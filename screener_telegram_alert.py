# Screener & Telegram Alert Bot with Volume Logic
# Features:
# - Accepts JSON coin data
# - Scores bullish/bearish including volume
# - Ranks top 10 in each
# - Sends summary + CSV to Telegram

import pandas as pd
import requests
import os
from io import BytesIO

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
        score += 1 if row.get('Volume USDT', 0) > 10_000_000 else 0
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

    top_bullish = df.sort_values(by='bullish_score', ascending=False).head(10)
    top_bearish = df.sort_values(by='bearish_score', ascending=False).head(10)

    return df, top_bullish, top_bearish

# ------------------------------
# TELEGRAM SENDER
# ------------------------------
def send_telegram_report(bot_token, chat_id, top_bullish, top_bearish, full_df):
    message = "\ud83d\udcca Screener Report\n\n"

    message += "\ud83d\udd25 Top 10 Bullish Coins:\n"
    for i, row in top_bullish.iterrows():
        vol = row.get('Volume USDT', 0)
        vol_str = f"${vol/1_000_000:.1f}M"
        message += f"{row['Symbol']} | +{row['Price Change % 24 hours']}% | RSI: {row['Relative Strength Index (14) 1 day']} | Vol: {vol_str} | Score: {row['bullish_score']}\n"

    message += "\n\u2744\ufe0f Top 10 Bearish Coins:\n"
    for i, row in top_bearish.iterrows():
        vol = row.get('Volume USDT', 0)
        vol_str = f"${vol/1_000_000:.1f}M"
        message += f"{row['Symbol']} | {row['Price Change % 24 hours']}% | RSI: {row['Relative Strength Index (14) 1 day']} | Vol: {vol_str} | Score: {row['bearish_score']}\n"

    # Send text
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

    # Send CSV file
    file_buffer = BytesIO()
    full_df.to_csv(file_buffer, index=False)
    file_buffer.seek(0)

    url_file = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {"document": ("screener_report.csv", file_buffer)}
    data = {"chat_id": chat_id}
    requests.post(url_file, files=files, data=data)

# ------------------------------
# EXAMPLE USAGE
# ------------------------------
if __name__ == "__main__":
    # Sample test data
    coins = [
        {"Symbol": "APEUSDT.P", "Price Change % 24 hours": 2.8, "Relative Strength Index (14) 1 day": 63, "Commodity Channel Index (20) 1 day": 154, "Momentum (10) 1 day": 0.35, "Volume USDT": 18000000},
        {"Symbol": "MASKUSDT.P", "Price Change % 24 hours": -4.1, "Relative Strength Index (14) 1 day": 35, "Commodity Channel Index (20) 1 day": -133, "Momentum (10) 1 day": -0.3, "Volume USDT": 950000},
        {"Symbol": "BNBUSDT.P", "Price Change % 24 hours": -2.9, "Relative Strength Index (14) 1 day": 41, "Commodity Channel Index (20) 1 day": -90, "Momentum (10) 1 day": -0.2, "Volume USDT": 48000000},
        {"Symbol": "ANIMEUSDT.P", "Price Change % 24 hours": 3.5, "Relative Strength Index (14) 1 day": 68, "Commodity Channel Index (20) 1 day": 121, "Momentum (10) 1 day": 0.27, "Volume USDT": 2200000},
        {"Symbol": "DOGEUSDT.P", "Price Change % 24 hours": -3.7, "Relative Strength Index (14) 1 day": 38, "Commodity Channel Index (20) 1 day": -145, "Momentum (10) 1 day": -0.4, "Volume USDT": 12000000}
    ]

    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    df, top_bulls, top_bears = score_coins(coins)
    send_telegram_report(BOT_TOKEN, CHAT_ID, top_bulls, top_bears, df)
