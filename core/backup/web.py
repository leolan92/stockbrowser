from flask import Flask, render_template, request, send_file
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
import os, sys
from pathlib import Path
from log import logger
import plotly.graph_objs as go
from plotly.offline import plot
import argparse

# BASE_DIR = Path(__file__).resolve().parent.parent.parent
HOME = Path.cwd()
STATIC_DIR = HOME / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = "db.sqlite"
IMG_PATH = STATIC_DIR / "chart.png"

app = Flask(__name__, 
            template_folder=str(HOME / "templates"), 
            static_folder=str(STATIC_DIR))

parser = argparse.ArgumentParser(description="Stock price web viewer", usage="python ./<...>/web.py -html | -i")
parser.add_argument("-m", "--mode", choices=["html", "interactive"], help="mode: html | interactive", required= True)
args = parser.parse_args()

MODE = args.mode

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

def plot_multiple_stocks(df, stock_ids, mode="price"):
    fig, ax1 = plt.subplots(figsize=(12, 6))

    if mode == "percentage":
        # 百分比模式
        for stock_id in stock_ids:
            df_sub = df[df["stock_id"] == stock_id].copy()
            base_price = df_sub["close"].iloc[0]
            df_sub["pct"] = (df_sub["close"] / base_price) * 100
            ax1.plot(df_sub["date"], df_sub["pct"], label=f"{stock_id}")
        ax1.set_ylabel("Price (% of first day)")
        ax1.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
        ax1.grid(True, axis="y", linestyle="--", alpha=0.7)

    else:
        # 雙 Y 軸模式
        cheap_stocks = []
        expensive_stocks = []
        for stock_id in stock_ids:
            latest_price = df[df["stock_id"] == stock_id]["close"].iloc[-1]
            if latest_price < 1000:
                cheap_stocks.append(stock_id)
            else:
                expensive_stocks.append(stock_id)

        # 左軸
        for stock_id in cheap_stocks:
            df_sub = df[df["stock_id"] == stock_id]
            ax1.plot(df_sub["date"], df_sub["close"], label=f"{stock_id} (L)")
        ax1.set_ylabel("Price (<1000 NTD)")
        ax1.grid(True, axis="y", linestyle="--", alpha=0.7)

        # 右軸
        if expensive_stocks:
            ax2 = ax1.twinx()
            for stock_id in expensive_stocks:
                df_sub = df[df["stock_id"] == stock_id]
                ax2.plot(df_sub["date"], df_sub["close"], label=f"{stock_id} (R)", linestyle="--")
            ax2.set_ylabel("Price (>=1000 NTD)")

            # 合併圖例
            lines, labels = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines + lines2, labels + labels2)
        else:
            ax1.legend()

    # 主刻度改為年份
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

# 不設定次刻度
    # ax1.xaxis.set_minor_locator(mticker.NullLocator())
    # ax1.xaxis.set_minor_formatter(mticker.NullFormatter())

# 格線用主刻度（年份）
    ax1.grid(True, axis="x", which="major", linestyle="--", alpha=0.5)

    plt.tick_params(axis="x", which="major", pad=10, labelsize=10)

    plt.title("Selected Stocks")
    plt.tight_layout()
    plt.savefig(IMG_PATH)
    plt.close()

def debug_plot(df, stock_ids, mode="price"):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    plt.figure(figsize=(10,5))
    plt.plot(df["date"], df["close"], label="close price")

    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    # plt.show()
    plt.savefig(IMG_PATH)

def plot_multiple_stocks2(df, stock_ids, mode="price"):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    df["date"] = pd.to_datetime(df["date"])

    fig, ax1 = plt.subplots(figsize=(15, 6))

    if mode == "percentage":
        for stock_id in stock_ids:
            df_sub = df[df["stock_id"] == stock_id].copy()
            df_sub["date"] = pd.to_datetime(df_sub["date"])  # 強制轉 datetime
            base_price = df_sub["close"].iloc[0]
            df_sub["pct"] = (df_sub["close"] / base_price) * 100
            ax1.plot(df_sub["date"], df_sub["pct"], label=f"{stock_id}")
        ax1.set_ylabel("Price (% of first day)")
        ax1.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
        ax1.grid(True, axis="y", linestyle="--", alpha=0.7)

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
            df_sub["date"] = pd.to_datetime(df_sub["date"])  # 強制轉 datetime
            ax1.plot(df_sub["date"], df_sub["close"], label=f"{stock_id} (L)")
        ax1.set_ylabel("Price (<1000 NTD)")
        ax1.grid(True, axis="y", linestyle="--", alpha=0.7)

        if expensive_stocks:
            ax2 = ax1.twinx()
            for stock_id in expensive_stocks:
                df_sub = df[df["stock_id"] == stock_id].copy()
                df_sub["date"] = pd.to_datetime(df_sub["date"])  # 強制轉 datetime
                ax2.plot(df_sub["date"], df_sub["close"], label=f"{stock_id} (R)", linestyle="--")
            ax2.set_ylabel("Price (>=1000 NTD)")

            lines, labels = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines + lines2, labels + labels2)
        else:
            ax1.legend()

    # X 軸時間設定
    date_range_years = (df["date"].max() - df["date"].min()).days / 365
    month_interval = 1 if date_range_years <= 2 else 3

    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=month_interval))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    ax1.xaxis.set_minor_locator(mdates.YearLocator())
    # 用之前的 FuncFormatter 來顯示年份，只在 1 月 1 日顯示
    ax1.xaxis.set_minor_formatter(
        mticker.FuncFormatter(
            lambda x, pos=None: mdates.num2date(x).strftime("\n%Y")
            if mdates.num2date(x).month == 1 and mdates.num2date(x).day == 1
            else ""
        )
    )

    ax1.grid(True, axis="x", which="major", linestyle="--", alpha=0.5)

    plt.tick_params(axis="x", which="major", pad=10, labelsize=9)
    plt.tick_params(axis="x", which="minor", pad=25, labelsize=10)

    plt.title("Selected Stocks")
    plt.tight_layout()
    plt.savefig(IMG_PATH)
    plt.close()


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
    selected = []
    mode = "price"

    if request.method == "POST":
        selected = request.form.getlist("stocks")
        mode = request.form.get("mode", "price")
        if selected:
            df = get_stock_data(selected)
            if MODE == "interactive":
                plot_div = plot_multiple_stocks_interactive(df, stock_ids=selected, mode=mode)
                return render_template("index.html", plot_div = plot_div)
            elif MODE == "html":
                # debug_plot(df, selected, mode=mode)
                plot_multiple_stocks2(df, selected, mode=mode)
                return render_template("index.html", chart_path = "chart.html")
            else:
                raise RuntimeError

        else:
            if IMG_PATH.exists():
                IMG_PATH.unlink()

    return render_template("index.html", stocks=all_stocks, selected=selected, mode=mode)

@app.route("/chart.png")
def chart_png():
    if os.path.exists(IMG_PATH):
        return send_file(IMG_PATH, mimetype="image/png")
    else:
        return "", 404

if __name__ == "__main__":
    
    app.run(debug=True, port=5001)
