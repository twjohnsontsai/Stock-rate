# app.py
import os
import io
import time
import requests
import datetime
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 使用非 GUI 后端，避免 RuntimeError
import matplotlib.pyplot as plt
import webbrowser
from flask import Flask, render_template, request

# ——————————————————————————————————————————————————————————————————————————
# 1. 静态文件夹挂到根路径
app = Flask(
    __name__,
    static_folder="output",   # 图表都保存到 output/
    static_url_path=""        # 挂在 / 也就是 http://.../xxx.png 能直接访问
)
# ——————————————————————————————————————————————————————————————————————————

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

TODAY      = datetime.date.today().strftime("%Y%m%d")
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
DEFAULT_DAYS = 60

def get_trading_days(n):
    days = []
    dt = datetime.date.today()
    while len(days) < n:
        if dt.weekday() < 5:
            days.append(dt.strftime("%Y%m%d"))
        dt -= datetime.timedelta(days=1)
    return list(reversed(days))

def fetch_institutional_data(dates, stock_no):
    recs = []
    api = "https://www.twse.com.tw/fund/T86?response=json&date={}&selectType=ALL"
    for d in dates:
        try:
            j = requests.get(api.format(d), timeout=5).json()
        except:
            continue
        if j.get('stat') != 'OK': 
            continue
        fields = j.get('fields', [])
        data   = j.get('data', [])
        if '證券代號' not in fields:
            continue
        idx  = fields.index('證券代號')
        try:
            f_idx = fields.index('外陸資買賣超股數(不含外資自營商)')
            i_idx = fields.index('投信買賣超股數')
            d_idx = fields.index('自營商買賣超股數')
        except ValueError:
            continue
        for row in data:
            if str(row[idx]).strip('=" ') == stock_no:
                recs.append({
                    'date':   pd.to_datetime(d, format="%Y%m%d"),
                    '外資':   int(str(row[f_idx]).replace(',', '')) // 1000,
                    '投信':   int(str(row[i_idx]).replace(',', '')) // 1000,
                    '自營商': int(str(row[d_idx]).replace(',', '')) // 1000,
                })
                break
        time.sleep(0.05)
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    return df.set_index('date').sort_index()

def fetch_price_data(dates, stock_no):
    # 如果前端一开始就没给 days，dates 可能为空
    if not dates:
        return pd.DataFrame()

    months = sorted({pd.to_datetime(d, format='%Y%m%d').strftime('%Y%m01') for d in dates})
    records = []
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={m}&stockNo={stock_no}"
        try:
            raw = requests.get(url, timeout=5).text
            lines = raw.splitlines()
            header = next(i for i, ln in enumerate(lines) if '日期' in ln)
            df = pd.read_csv(io.StringIO('\n'.join(lines[header:])), encoding='big5')
        except:
            continue
        df.columns = [c.strip() for c in df.columns]
        df = df[df['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$')]
        ymd = df['日期'].str.split('/', expand=True).astype(int)
        df['date'] = [datetime.date(y+1911, mm, dd) 
                      for y, mm, dd in zip(ymd[0], ymd[1], ymd[2])]
        df['收盤價'] = pd.to_numeric(df['收盤價'].astype(str).str.replace(',', ''), errors='coerce')
        df['成交量'] = pd.to_numeric(df['成交股數'].astype(str).str.replace(',', ''), errors='coerce') // 1000
        records.append(df[['date','收盤價','成交量']])
        time.sleep(0.05)

    # 如果一条都没抓到，直接返回空 DF
    if not records:
        return pd.DataFrame()

    dfp = pd.concat(records)\
            .drop_duplicates('date')\
            .set_index('date')\
            .sort_index()
    return dfp

@app.route("/", methods=["GET","POST"])
def index():
    chart_file = None
    msg = None

    if request.method == "POST":
        stock_no = request.form.get("stock_no","").strip()
        days_str = request.form.get("days","").strip()
        # 2. 默认值保护
        if days_str.isdigit():
            days = int(days_str)
        else:
            days = DEFAULT_DAYS

        if not stock_no:
            msg = "請輸入股票代號"
        else:
            dates   = get_trading_days(days)
            df_i    = fetch_institutional_data(dates, stock_no)
            df_p    = fetch_price_data(dates, stock_no)
            df      = df_i.join(df_p, how="inner")

            if df.empty:
                msg = "查無資料或網路超時"
            else:
                # 3. 画图
                fig_w = max(12, len(df)*0.24)
                fig, ax1 = plt.subplots(figsize=(fig_w,5))
                x = list(range(len(df)))

                ax1.plot(x, df['外資'].values, label='外資', color='blue')
                ax1.plot(x, df['投信'].values, label='投信', color='orange', linestyle='--')
                ax1.plot(x, df['自營商'].values, label='自營商', color='green', linestyle=':')
                ax1.set_ylabel("法人買賣超 (張)")
                ax1.grid(True, linestyle="--", alpha=0.3)

                ax2 = ax1.twinx()
                ax2.plot(x, df['收盤價'].values, color='red', label='收盤價')
                ax2.set_ylabel("收盤價", color='red')
                ax2.tick_params(axis='y', labelcolor='red')

                ax3 = ax1.twinx()
                ax3.spines['right'].set_position(('outward',60))
                ax3.bar(x, df['成交量'].values, color='gray', alpha=0.3, width=0.6)
                ax3.set_ylabel("成交量 (張)", color='gray')
                ax3.tick_params(axis='y', labelcolor='gray')

                labels = [d.strftime("%m/%d") for d in df.index]
                ax1.set_xticks(x)
                ax1.set_xticklabels(labels, rotation=45, fontsize=8)
                ax1.set_xlim(-0.5, len(x)-0.5)

                lines1, lbls1 = ax1.get_legend_handles_labels()
                lines2, lbls2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1+lines2, lbls1+lbls2, loc='upper left')

                plt.title(f"{stock_no}｜法人買賣超、收盤價、成交量（近{days}交易日）")
                fig.tight_layout()

                filename = f"{stock_no}_chart_{TODAY}.png"
                filepath = os.path.join(OUTPUT_DIR, filename)
                plt.savefig(filepath, dpi=300, bbox_inches="tight")
                plt.close(fig)

                chart_file = filename

    return render_template("index.html",
                           chart_file=chart_file,
                           msg=msg)

if __name__ == "__main__":
    # 浏览器自动打开
    webbrowser.open("http://127.0.0.1:5000")
    # 生产请用 WSGI
    app.run(debug=True, use_reloader=False)
