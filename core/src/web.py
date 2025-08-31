#! /usr/bin/env python

from flask import Flask, render_template, request, send_file
from flask import redirect, url_for
import pandas as pd
# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.dates as mdates
# import matplotlib.ticker as mticker
# import matplotlib.pyplot as plt
import os, sys
from pathlib import Path
from .log import logger
import plotly.graph_objs as go
from plotly.offline import plot
import argparse
from . import db
import datetime

# debugging
debug = 0

# Init DB
db.init_db(debug = debug)
status = db.check_db_status()
logger.info(f"目前資料庫狀態: {status}")

# BASE_DIR = Path(__file__).resolve().parent.parent.parent
HOME = Path.cwd()
STATIC_DIR = HOME / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = "db.sqlite"

app = Flask(__name__, 
            template_folder=str(HOME / "templates"), 
            static_folder=str(STATIC_DIR))

#    print("DEBUG JSON:", data)
#    print("Final URL:", r.url)   # 看最後請求的網址
#    print("Status Code:", r.status_code)
#    print("Response JSON:", r.json())

def get_gold_history_usd():
    """模擬黃金價格歷史（這裡假資料，等你有 Metals API Key 再換）"""
    dates = pd.date_range(start=start_date, end=end_date)
    # 假資料：隨機波動 around 1900 USD/oz
    prices = 1900 + (pd.Series(range(len(dates))).apply(lambda x: (x % 10 - 5) * 2))
    return pd.DataFrame({"date": dates, "gold_usd": prices})


def plot_rates_history(df, selected_rates, mode):
    # df = get_usd_twd_history()
    # df = db.load_exchange_rate()
    if df.empty:
        logger.warning("DB 中沒有匯率資料，請先更新資料")
        return "<p>無匯率資料</p>"
    fig = go.Figure()
    
    for rate in selected_rates:
        df_sub = df[df["base_currency"] == rate].copy()        
        fig.add_trace(go.Scatter(
            x=df_sub["date"],
            y=df_sub["rate"],
            name=f"TWD/{rate}",
            mode="lines+markers",
        ))
    fig.update_layout(title="匯率走勢", 
                      xaxis_title="日期", 
                      yaxis_title="匯率",
                      autosize=True,
                      height=None,
                      margin=dict(l=20, r=20, t=20, b=20))
    # return plot(fig, output_type="div", include_plotlyjs="cdn")
    # 回傳物件 後續對大小修改
    return fig


def plot_gold_history(usd_twd_df):
    df = get_gold_history_usd()
    usd_to_twd = usd_twd_df["usd_twd"]
    df["gold_twd"] = df["gold_usd"] * usd_to_twd
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["gold_twd"],
        mode="lines",
        name="Gold (TWD/oz)"
    ))
    fig.update_layout(title="黃金價格 (TWD/oz) 走勢", xaxis_title="日期", yaxis_title="台幣/盎司")
    # return plot(fig, output_type="div", include_plotlyjs=False)
    # 回傳物件 後續對大小修改
    return fig


def plot_multiple_stocks(df, stock_ids, mode="price"):
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
                hovertemplate="日期: %{x|%Y-%m-%d}<br>價格比例: %{y:.2f}%<extra></extra>",
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
            autosize=True,
            height=None,
            margin=dict(l=20, r=20, t=20, b=20) , # 避免 overflow           
            yaxis2=dict(
                title="Price (>=1000 NTD)",
                overlaying="y",
                side="right",
            )
        )

    fig.update_layout(
        title="股票走勢圖",
        xaxis_title="日期",
        hovermode="x unified",  # 所有股票同步顯示
        template="plotly_white",
        autosize=True,
        height=None,        
        margin=dict(l=20, r=20, t=20, b=20)  # 避免 overflow
    )

    # 回傳 HTML 片段（可嵌進 Flask 頁面）
    # return plot(fig, output_type="div", include_plotlyjs="cdn")
    # 回傳物件 後續對大小修改
    return fig


@app.route("/add_stock", methods=["POST"])
def add_stock():
    stock_id = request.form.get("stock_id", "").strip()
    if stock_id:
        try:
            df = db.fetch_stock_data(stock_id)  # 你現有的 API 取得函數
            db.save_stock_to_db(stock_id, df)        # 你現有的存 DB 函數
            logger.info(f"新增股票 {stock_id} 成功")
        except Exception as e:
            logger.error(f"新增股票 {stock_id} 失敗: {e}")
    return redirect(url_for("index"))


@app.route("/add_ER", methods=["POST"])
def add_ER():
    ER_id = request.form.get("ER_id", "").strip()
    if ER_id:
        try:
            df = db.fetch_exchange_rate_from_api(ER_id, "TWD")  # 你現有的 API 取得函數
            db.save_exchange_rate(ER_id, "TWD" ,df)        # 你現有的存 DB 函數
            logger.info(f"新增幣別 {ER_id} 成功")
        except Exception as e:
            logger.error(f"新增幣別 {ER_id} 失敗: {e}")
    return redirect(url_for("index"))


@app.route("/add_event", methods=["POST"])
def add_event():
    event_date = request.form.get("event_date")
    title = request.form.get("title", "").strip()
    if event_date and title:
        try:
            db.save_event(event_date, title)  # 自己實作存 DB 的函數
            logger.info(f"新增事件: {event_date} {title}")
        except Exception as e:
            logger.error(f"新增事件失敗: {e}")
    return redirect(url_for("index"))

@app.route("/clear_db", methods=["POST"])
def clear_database():
    table = request.form.get("table", None)  # 從前端抓要清空哪個表，沒填就是清空全部
    try:
        db.clear_db(table)
        logger.info("資料庫已清空")
    except Exception as e:
        logger.error(f"清空資料庫失敗: {e}")
    return redirect(url_for("index"))


@app.route("/", methods=["GET", "POST"])
def index():
    # 初始化
    all_stocks = db.get_all_stocks()
    selected_stocks = request.form.getlist("stocks") if request.method == "POST" else []

    all_rates = db.get_all_rates()
    selected_rates = request.form.getlist("rates") if request.method == "POST" else []

    # 初始化 DataFrame 和回傳資料
    df_stock = pd.DataFrame()
    df_rates = pd.DataFrame()

    stock_data = {"date": [], "values": []}
    usd_twd_data = {"date": [], "values": []}
    gold_data = {"date": [], "values": []}

    mode = request.form.get("mode", "price")

    print(f"selected_stocks : {selected_stocks}")

    # 股票圖
    fig_stock = None
    if selected_stocks:
        df_stock = db.load_stocks_from_db(selected_stocks)
        if not df_stock.empty:
            # --- Plotly
            fig_stock = plot_multiple_stocks(df_stock, selected_stocks, mode)
            fig_stock = fig_stock.to_html(full_html=False, config={"responsive": True})

            # --- Echart
            # --- 股票資料 ---
            # 1) 確保日期是 datetime
            df_stock["date"] = pd.to_datetime(df_stock["date"])

            # 2) 轉寬表：每個 stock_id 一欄
            piv = (
                df_stock.pivot_table(
                    index="date", columns="stock_id", values="close", aggfunc="last"
                ).sort_index()
            )

            # 3) 百分比模式（以各自第一個非空值為基準）
            if mode == "percentage":
                base = piv.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else None)
                piv = (piv / base) * 100

            # 4) 組 ECharts 需要的資料
            dates = [d.strftime("%Y-%m-%d") for d in piv.index]
            values = {
                str(col): piv[col].where(piv[col].notna(), None).tolist()
                for col in piv.columns
            }
            stock_data = {"dates": dates, "values": values}

    # 匯率 & 黃金（歷史走勢
    fig_usd_twd = None
    if selected_rates:
        df_rates = db.load_rates_from_db(selected_rates)
        if not df_rates.empty:
            # --- Plotly
            fig_usd_twd = plot_rates_history(df_rates, selected_rates, mode)
            fig_usd_twd= fig_usd_twd.to_html(full_html=False, config={"responsive": True})

            # --- Echart
            df_rates["date"] = pd.to_datetime(df_rates["date"])
            piv_r = (
                df_rates.pivot_table(
                    index="date", columns="base_currency", values="rate", aggfunc="last"
                ).sort_index()
            )
            if mode == "percentage":
                base = piv_r.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else None)
                piv_r = (piv_r / base) * 100

            dates_r = [d.strftime("%Y-%m-%d") for d in piv_r.index]
            values_r = {
                str(col): piv_r[col].where(piv_r[col].notna(), None).tolist()
                for col in piv_r.columns
            }
            usd_twd_data = {"dates": dates_r, "values": values_r}


    # fig_gold = plot_gold_history(get_usd_twd_history())
    fig_gold = None
    gold_data = {"dates": [], "values": []}

    # event
    events_df = db.load_events()  # 回傳 DataFrame，有 columns: date, title
    events = [
        {"date": d.strftime("%Y-%m-%d") if isinstance(d, datetime.date) else d, "title": t}
        for d, t in zip(events_df["event_date"], events_df["title"])
    ] if not events_df.empty else []

    return render_template(
        "index.html",
        stocks=all_stocks,
        rates=all_rates,
        selected_stocks=selected_stocks,
        selected_rates=selected_rates,
        mode=mode,
        stock_data=stock_data,
        usd_twd_data=usd_twd_data,
        gold_data=gold_data,
        events=events,
    )

#    return render_template(
#        "index.html",
#        stocks=all_stocks,
#        rates=all_rates,
#        selected_stocks=selected_stocks,
#        fig_stock=fig_stock,
#        fig_usd_twd=fig_usd_twd,
#        fig_gold=fig_gold,        
#        mode=mode
#    )



if __name__ == "__main__":
    app.run(debug=True, port=5001)
