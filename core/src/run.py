#! /usr/bin/env pytingn

import sqlite3
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import webbrowser
import argparse
import os, sys
from .log import logger

DB_FILE = "db.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS stock_prices (
        stock_id TEXT,
        date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (stock_id, date)
    )
    """)
    conn.commit()
    conn.close()

def fetch_stock_data(stock_id, start="2015-01-01"):
    ticker = f"{stock_id}.TW"
    df = yf.download(ticker, start=start)
    if df is None or df.empty:
        raise ValueError(f"Cannot get {stock_id} data, please check stock ID or time period")
    
    df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    logger.info("Fetching stock data...")
    logger.info("Preview of df:")
    logger.info(f"\n{df.head()}")
    return df

def get_record_count(stock_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stock_prices WHERE stock_id=?", (stock_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def save_to_db(stock_id, df):
    before_count = get_record_count(stock_id)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for _, row in df.iterrows():
        try:
            c.execute("""
            INSERT OR REPLACE INTO stock_prices (stock_id, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (stock_id, row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"])))
        except Exception as e:
            logger.error(f"Error inserting row: {e}")
            return
    conn.commit()
    conn.close()

    after_count = get_record_count(stock_id)
    added_count = after_count - before_count
    db_size = os.path.getsize(DB_FILE) / 1024  # KB

    logger.info(f"Added new data {added_count} count")
    if db_size > 1024:
        logger.info(f"DB size：{db_size/1024:.2f} MB")
    else:
        logger.info(f"DB size：{db_size:.2f} KB")

def load_from_db(stock_id):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        f"SELECT * FROM stock_prices WHERE stock_id = '{stock_id}' ORDER BY date",
        conn
    )
    conn.close()
    return df

def plot_stock(df, stock_id):
    plt.figure(figsize=(10,5))
    plt.plot(df["date"], df["close"], label="Close Price")
    plt.title(f"{stock_id} Close Price")
    plt.xlabel("Date")
    plt.ylabel("Price (NTD)")
    plt.legend()
    plt.grid(True)
    img_path = "chart.png"
    plt.savefig(img_path)
    plt.close()

    html_path = "chart.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(f"<html><body><h1>{stock_id} Stock trend </h1><img src='{img_path}'></body></html>")

    webbrowser.open(f"file://{os.path.abspath(html_path)}")

def main():
    parser = argparse.ArgumentParser(description="Stock price html viewer", usage="python -m core <action> <stock_id>\n Ex:: python -m core update 2330")
    parser.add_argument("action", choices=["update", "show"], help="Input：update / show")
    parser.add_argument("stock_id", help="Stock id, ex: 2330")
    # 如果沒給任何參數，顯示 help
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    init_db()

    if args.action == "update":
        logger.info(f"Fetching {args.stock_id} data...")
        df = fetch_stock_data(args.stock_id)
        save_to_db(args.stock_id, df)
        logger.info("Done Updating!")

    elif args.action == "show":
        df = load_from_db(args.stock_id)
        if df.empty:
            logger.warning("No data in DB, please update first")
        else:
            plot_stock(df, args.stock_id)

if __name__ == "__main__":
    main()
