# app_bwi_full.py
from flask import Flask, render_template, request
import os
import io
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# 中文顯示
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# ---- 抓取千張大戶比例 ----
def fetch_thousand_ratio(date):
    url = f"https://www.twse.com.tw/fund/BWIBBU_d?response=csv&date={date}&selectType=ALL"
    res = requests.get(url)
    if res.ok:
        return res.text
    return None

def parse_thousand_ratio(csv_text, stock_id):
    df = pd.read_csv(io.StringIO(csv_text.replace('"', '')), header=1)
    df = df[df['證券代號'] == stock_id]
    if not df.empty:
        return float(df.iloc[0]['千張大戶持股比率(%)'])
    return None

def get_recent_dates(days):
    today = datetime.today()
    result = []
    while len(result) < days:
        if today.weekday() < 5:  # weekday
            result.append(today.strftime('%Y%m%d'))
        today -= timedelta(days=1)
    return result[::-1]  # oldest to newest

# ---- 抓取 T86 三大法人買賣超 ----
def fetch_t86(date):
    url = f"https://www.twse.com.tw/fund/T86?response=csv&date={date}&selectType=ALLBUT0999"
    res = requests.get(url)
    return res.text if res.ok else None

def parse_t86(csv_text, stock_id):
    df = pd.read_csv(io.StringIO(csv_text.replace('"','')), header=1)
    df = df[df['證券代號'] == stock_id]
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        '外資': int(str(row['外陸資買賣超股數']).replace(',', '')) / 1000,  # 張
        '投信': int(str(row['投信買賣超股數']).replace(',', '')) / 1000,
        '自營商': int(str(row['自營商買賣超股數']).replace(',', '')) / 1000,
    }

# ---- 抓取收盤價 ----
def fetch_price_data(stock_id, date):
    y, m = date[:4], date[4:6]
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={y}{m}01&stockNo={stock_id}"
    res = requests.get(url)
    return res.text if res.ok else None

def parse_price_data(csv_text, target_date):
    df = pd.read_csv(io.StringIO(csv_text.replace('"','')), header=1)
    df.columns = [col.strip() for col in df.columns]
    df = df.dropna()
    df['日期'] = df['日期'].str.replace('/', '-')
    df = df[df['日期'].str.replace('-', '') == target_date]
    if df.empty:
        return None
    return float(str(df.iloc[0]['收盤價']).replace(',', ''))

# ---- 分析與繪圖 ----
@app.route('/', methods=['GET', 'POST'])
def index():
    chart_path = None
    if request.method == 'POST':
        stock_id = request.form['stock_id']
        days = int(request.form['days'])

        dates = get_recent_dates(days)
        thousand_ratios, foreigns, trusts, dealers, prices = [], [], [], [], []
        
        for d in dates:
            ratio = None
            t86 = None
            price = None

            try:
                text = fetch_thousand_ratio(d)
                if text:
                    ratio = parse_thousand_ratio(text, stock_id)
            except: pass

            try:
                text = fetch_t86(d)
                if text:
                    t86 = parse_t86(text, stock_id)
            except: pass

            try:
                text = fetch_price_data(stock_id, d)
                if text:
                    price = parse_price_data(text, d)
            except: pass

            thousand_ratios.append(ratio if ratio else None)
            foreigns.append(t86['外資'] if t86 else None)
            trusts.append(t86['投信'] if t86 else None)
            dealers.append(t86['自營商'] if t86 else None)
            prices.append(price if price else None)

        # 繪圖
        fig, ax1 = plt.subplots(figsize=(12, 6))
        ax2 = ax1.twinx()
        x = range(len(dates))

        ax1.plot(x, thousand_ratios, label='千張大戶比例(%)', marker='o')
        ax1.plot(x, pd.Series(foreigns).cumsum(), label='外資持股變動(累積張)', linestyle='--')
        ax1.plot(x, pd.Series(trusts).cumsum(), label='投信持股變動(累積張)', linestyle='--')
        ax1.plot(x, pd.Series(dealers).cumsum(), label='自營商持股變動(累積張)', linestyle='--')
        ax1.set_ylabel('持股比例 / 持股變動')
        ax1.legend(loc='upper left')

        ax2.plot(x, prices, label='收盤價', color='black')
        ax2.set_ylabel('股價')
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.0f}'))

        ax1.set_xticks(x)
        ax1.set_xticklabels([d[4:] for d in dates], rotation=45)
        ax1.set_title(f"{stock_id}｜千張大戶與三大法人比較")

        os.makedirs('static', exist_ok=True)
        chart_path = f'static/{stock_id}_compare.png'
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()

    return render_template('index_bwi.html', chart_path=chart_path)

if __name__ == '__main__':
    app.run(debug=True)
