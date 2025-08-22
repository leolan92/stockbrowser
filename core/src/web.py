
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
# import matplotlib.dates as mdates
# import matplotlib.ticker as mticker
# import matplotlib.pyplot as plt
import os, sys
from pathlib import Path
from log import logger
import plotly.graph_objs as go
from plotly.offline import plot
import argparse
import requests

# BASE_DIR = Path(__file__).resolve().parent.parent.parent
HOME = Path.cwd()
STATIC_DIR = HOME / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = "db.sqlite"
IMG_PATH = STATIC_DIR / "chart.png"

app = Flask(__name__, 
            template_folder=str(HOME / "templates"), 
            static_folder=str(STATIC_DIR))

# parser = argparse.ArgumentParser(description="Stock price web viewer", usage="python ./<...>/web.py -html | -i")
# parser.add_argument("-m", "--mode", choices=["html", "interactive"], help="mode: html | interactive", required= True)
# args = parser.parse_args()

def get_all_stocks():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT DISTINCT stock_id FROM stock_prices", conn)
    conn.close()
    return df["stock_id"].tolist()

def get_stock_data(stock_ids):
    conn = sqlite3.connect(DB_FILE)
    placeholder = ",".join("?" for _ in stock_ids)
    sql = f"""
    SELECT * FROM stock_prices
    WHERE stock_id IN ({placeholder})
    ORDER BY date
    """
    df = pd.read_sql_query(sql, conn, params=stock_ids)
    conn.close()
    logger.info("Querying stock data from DB...")
    logger.info("Preview of df:")
    logger.info(f"\n{df.head()}")
    return df

def get_usd_twd_history(days=90):
    """抓取最近 N 天的美元對台幣匯率"""
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)
    url = f"https://api.exchangerate.host/timeseries?start_date={start_date}&end_date={end_date}&base=USD&symbols=TWD"
    r = requests.get(url)
    data = r.json()

    print("DEBUG JSON:", data)
    print("Final URL:", r.url)   # 看最後請求的網址
    print("Status Code:", r.status_code)
    print("Response JSON:", r.json())
    
    dates = []
    rates = []
    for date, rate in sorted(data["rates"].items()):
        dates.append(date)
        rates.append(rate["TWD"])
    return pd.DataFrame({"date": dates, "usd_twd": rates})


def get_gold_history_usd(days=90):
    """模擬黃金價格歷史（這裡假資料，等你有 Metals API Key 再換）"""
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date)
    # 假資料：隨機波動 around 1900 USD/oz
    prices = 1900 + (pd.Series(range(len(dates))).apply(lambda x: (x % 10 - 5) * 2))
    return pd.DataFrame({"date": dates, "gold_usd": prices})


def plot_usd_twd_history():
    df = get_usd_twd_history()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["usd_twd"],
        mode="lines",
        name="USD/TWD"
    ))
    fig.update_layout(title="USD/TWD 匯率走勢", xaxis_title="日期", yaxis_title="匯率")
    return plot(fig, output_type="div", include_plotlyjs=False)


def plot_gold_history():
    df = get_gold_history_usd()
    usd_to_twd = get_usd_to_twd()
    df["gold_twd"] = df["gold_usd"] * usd_to_twd
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["gold_twd"],
        mode="lines",
        name="Gold (TWD/oz)"
    ))
    fig.update_layout(title="黃金價格 (TWD/oz) 走勢", xaxis_title="日期", yaxis_title="台幣/盎司")
    return plot(fig, output_type="div", include_plotlyjs=False)


def plot_multiple_stocks_interactive(df, stock_ids, mode="price"):
    fig = go.Figure()

    if mode == "percentage":
        for stock_id in stock_ids:
            df_sub = df[df["stock_id"] == stock_id].copy()
            base_price = df_sub["close"].iloc[0]
            df_sub["pct"] = (df_sub["close"] / base_price) * 100
            fig.add_trace(go.Scatter(
                x=df_sub["date"],
                y=df_sub["pct"],
                mode="lines+markers",
                name=f"{stock_id}",
                hovertemplate="日期: %{x|%Y-%m-%d}<br>價格比例: %{y:.2f}%<extra></extra>"
            ))
        fig.update_yaxes(title="Price (% of first day)")
    else:
        cheap_stocks = []
        expensive_stocks = []
        for stock_id in stock_ids:
            latest_price = df[df["stock_id"] == stock_id]["close"].iloc[-1]
            if latest_price < 1000:
                cheap_stocks.append(stock_id)
            else:
                expensive_stocks.append(stock_id)

        for stock_id in cheap_stocks:
            df_sub = df[df["stock_id"] == stock_id].copy()
            fig.add_trace(go.Scatter(
                x=df_sub["date"],
                y=df_sub["close"],
                mode="lines+markers",
                name=f"{stock_id} (L)",
                hovertemplate="日期: %{x|%Y-%m-%d}<br>收盤價: %{y:.2f} 元<extra></extra>",
                yaxis = "y1",
            ))

        for stock_id in expensive_stocks:
            df_sub = df[df["stock_id"] == stock_id].copy()
            fig.add_trace(go.Scatter(
                x=df_sub["date"],
                y=df_sub["close"],
                mode="lines+markers",
                name=f"{stock_id}",
                hovertemplate="日期: %{x|%Y-%m-%d}<br>收盤價: %{y:.2f} 元<extra></extra>",
                yaxis = "y2",
            ))
        fig.update_layout(
            yaxis=dict(title="Price (<1000 NTD)"),
            yaxis2=dict(
                title="Price (>=1000 NTD)",
                overlaying="y",
                side="right"
            )
        )

    fig.update_layout(
        title="股票走勢圖",
        xaxis_title="日期",
        hovermode="x unified",  # 所有股票同步顯示
        template="plotly_white"
    )

    # 回傳 HTML 片段（可嵌進 Flask 頁面）
    return plot(fig, output_type="div", include_plotlyjs="cdn")

@app.route("/", methods=["GET", "POST"])
def index():
    all_stocks = get_all_stocks()
    
    # 初始化
    selected_stocks = []
    mode = "price"

    if request.method == "POST":
        # 從表單抓股票清單與模式
        selected_stocks = request.form.getlist("stocks")
        mode = request.form.get("mode", "price")
    
    # 如果有選股票就抓資料
    # df = get_stock_data(selected_stocks) if selected_stocks else None
    # if df is not None and not df.empty:
    #     plot_div = plot_multiple_stocks_interactive(df, stock_ids=selected_stocks, mode=mode)
    # else:
    #     plot_div = None

    # 股票圖
    df = get_stock_data(selected_stocks) if selected_stocks else None
    if df is not None and not df.empty:
        fig_stock = plot_multiple_stocks_interactive(df, stock_ids=selected_stocks, mode=mode)
    else:
        fig_stock = None

    # 匯率 & 黃金（歷史走勢）
    fig_usd_twd = plot_usd_twd_history()
    fig_gold = plot_gold_history()

    return render_template(
        "index.html",
        stocks=all_stocks,
        selected_stocks=selected_stocks,
        fig_stock=fig_stock,
        fig_usd_twd=fig_usd_twd,
        fig_gold=fig_gold,
        mode=mode
    )

if __name__ == "__main__":
    app.run(debug=True, port=5001)
