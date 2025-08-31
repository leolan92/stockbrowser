#! /usr/bin/env python

import sqlite3
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import webbrowser
import argparse
import os, sys
from .log import logger
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

DB_FILE = "db.sqlite"
end_date = datetime.today().date()
start_date = end_date - timedelta(days = 365*10)

# 載入 .env
load_dotenv()
# 讀取 API_KEY
EXCHANGERATEHOST_api_key = os.getenv("EXCHANGERATEHOST_API_KEY")
CURRENCYFREAKS_API_KEY = os.getenv("CURRENCYFREAKS_API_KEY")

def init_db(debug = 0):
    """
    初始化資料庫，建立 stock_prices、exchange_rate 與 gold_prices 表
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 股票價格表
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
        );
    """)

    # 匯率表
    c.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rate (
            base_currency TEXT,
            target_currency TEXT,
            date TEXT,
            rate REAL,
            PRIMARY KEY (base_currency, target_currency, date)
        );
    """)

    # 黃金/貴金屬表 (暫留接口)
    c.execute("""
        CREATE TABLE IF NOT EXISTS gold_prices (
            symbol TEXT,
            date TEXT,
            price REAL,
            PRIMARY KEY (symbol, date)
        );
    """)

    # 事件表
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date DATE NOT NULL,
            title TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()

    if os.path.exists(DB_FILE):
        logger.info("資料庫初始化完成")
    else:
        logger.warning("資料庫建立失敗，請檢查權限或路徑")

    if debug:
        df = load_stocks_from_db(stock_ids = get_all_stocks())
        print(f"DEBUG: df -->\n {df.head()}")


def fetch_stock_data(stock_id):
    ticker = f"{stock_id}.TW"
    df = yf.download(ticker, start=start_date)
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
    logger.info(f"成功抓取 {stock_id} 股票資料")
    return df

def get_record_count(stock_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stock_prices WHERE stock_id=?", (stock_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_stocks():
    """
    回傳 DB 內所有股票 ID
    """
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT DISTINCT stock_id FROM stock_prices", conn)
    conn.close()
    return df["stock_id"].tolist()

def get_all_rates():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT DISTINCT base_currency FROM exchange_rate",
        conn
    )
    conn.close()
    return df["base_currency"].tolist()

def save_stock_to_db(stock_id, df):
    """
    將股票資料寫入資料庫
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    before_count = get_record_count(stock_id)    

    for _, row in df.iterrows():
        c.execute("""
            INSERT OR REPLACE INTO stock_prices (stock_id, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (stock_id, row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"])))

    conn.commit()
    conn.close()
    logger.info(f"{stock_id} 資料已更新到資料庫")
    after_count = get_record_count(stock_id)
    added_count = after_count - before_count
    db_size = os.path.getsize(DB_FILE) / 1024  # KB

    logger.info(f"Added new data {added_count} count")
    if db_size > 1024:
        logger.info(f"DB size：{db_size/1024:.2f} MB")
    else:
        logger.info(f"DB size：{db_size:.2f} KB")

def load_stocks_from_db(stock_ids):
    """
    回傳多個股票的完整 DataFrame
    """
    conn = sqlite3.connect(DB_FILE)
    placeholder = ",".join("?" for _ in stock_ids)
    sql = f"""
        SELECT * FROM stock_prices
        WHERE stock_id IN ({placeholder})
        ORDER BY date
    """
    df = pd.read_sql_query(sql, conn, params=stock_ids)
    conn.close()
    return df

# =========================
# 匯率處理
# =========================
def save_exchange_rate(base, target, df):
    """
    將匯率資料寫入資料庫
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for _, row in df.iterrows():
        c.execute("""
            INSERT OR REPLACE INTO exchange_rate (base_currency, target_currency, date, rate)
            VALUES (?, ?, ?, ?)
        """, (base, target, row["date"], row["rate"]))
    conn.commit()
    conn.close()
    logger.info(f"匯率 {base}/{target} 已存入資料庫")

def fetch_exchange_rate_from_api(base="USD", target="TWD"):
    """
    從 API 下載匯率資料，回傳 DataFrame
    """
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=365)
    # --- max: 365day
    url = (
        "https://api.exchangerate.host/timeframe"
        f"?start_date={start_date}"
        f"&end_date={end_date}"
        f"&source={base}"
        f"&currencies={target}"
        f"&access_key={EXCHANGERATEHOST_api_key}"
    )
    logger.info(f"呼叫 API 抓取 {base}/{target} 匯率資料")
    logger.info(f"呼叫的 API URL: {url}")
    response = requests.get(url)
    data = response.json()

    # --- max: 365days,too
#     url = f"/v2.0/timeseries?startDate={start_date}&endDate={end_date}&base={base}&symbols={target}&apikey={CURRENCYFREAKS_API_KEY}"
#     conn = http.client.HTTPSConnection("api.currencyfreaks.com")
#     payload = ''
#     headers = {}
#     conn.request("GET", url, payload, headers)
#     res = conn.getresponse()
#     data = res.read()
#     print(data.decode("utf-8"))

    if "quotes" not in data:
        logger.error(f"API 回傳格式異常: {data}")
        raise ValueError("Invalid API response for exchange rate")

    dates = []
    rates = []
    for date, rate in sorted(data["quotes"].items()):
        key = f"{base}{target}"
        if key in rate:
            dates.append(date)
            rates.append(rate[key])

    df = pd.DataFrame({"date": dates, "rate": rates})
    return df


def load_rates_from_db(rates):
    """
    回傳多個股票的完整 DataFrame
    """
    conn = sqlite3.connect(DB_FILE)
    placeholder = ",".join("?" for _ in rates)
    sql = f"""
        SELECT * FROM exchange_rate
        WHERE base_currency IN ({placeholder})
        ORDER BY date
    """
    df = pd.read_sql_query(sql, conn, params=rates)
    conn.close()
    return df

def load_exchange_rate():
    """
    從資料庫讀取匯率，如果沒有就自動抓取 API 並存入 DB
    """
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(
            """
            SELECT date, rate FROM exchange_rate
            ORDER BY date
            """,
            conn,
        )
    except Exception as e:
        logger.error(f"讀取 DB 錯誤: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    # 如果資料庫沒有資料，抓 API 並存檔
    if df.empty:
        logger.warning(f"資料庫沒有匯率，嘗試從 API 下載")
        base, target = "USD", "TWD"
        df = fetch_exchange_rate_from_api(base, target)
        save_exchange_rate(base, target, df)
    else:
        logger.info(f"從資料庫讀取匯率，共 {len(df)} 筆資料")

    return df

# =========================
# 黃金 / 貴金屬接口
# =========================
def save_gold_to_db(symbol, df):
    """
    將黃金或貴金屬資料寫入資料庫
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for _, row in df.iterrows():
        c.execute("""
            INSERT OR REPLACE INTO gold_prices (symbol, date, price)
            VALUES (?, ?, ?)
        """, (symbol, row["date"], row["price"]))
    conn.commit()
    conn.close()
    logger.info(f"{symbol} 貴金屬資料已存入資料庫")

def load_gold_from_db(symbol):
    """
    從資料庫讀取黃金或貴金屬資料
    """
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM gold_prices WHERE symbol = ? ORDER BY date",
        conn,
        params=(symbol,)
    )
    conn.close()
    return df

# =========================
# 事件表
# =========================
def save_event(date_str, title):
    """存事件到資料庫"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO events (event_date, title) VALUES (?, ?)", (date_str, title))
    conn.commit()
    conn.close()

def load_events():
    """讀取事件資料"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT event_date, title FROM events ORDER BY event_date", conn)
    conn.close()
    return df

# =========================
# 資料庫相關
# =========================
def clear_db(table=None):
    """
    清空資料庫
    :param table: 指定要清空的表格名稱
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if table:
        logger.warning(f"清空 {table} 資料...")
        c.execute(f"DELETE FROM {table}")
    
    conn.commit()
    conn.close()

def check_db_status():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    tables = ["stock_prices", "exchange_rate", "gold_prices"]
    status = {}

    for table in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            status[table] = c.fetchone()[0]
        except sqlite3.Error:
            status[table] = None

    conn.close()
    return status

if __name__ == "__main__":
    init_db()
    logger.info("資料庫初始化完成")

