import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import os
from datetime import datetime, timedelta

# 中文顯示
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# 輸出資料夾
OUTPUT_FOLDER = './output'
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def fetch_bwibbu_csv(date_str):
    url = f"https://www.twse.com.tw/fund/BWIBBU_d?response=csv&date={date_str}&selectType=ALL"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    if r.status_code == 200 and len(r.text) > 100:
        return r.text
    return None

def parse_thousand_ratio(csv_text, stock_id):
    df = pd.read_csv(io.StringIO(csv_text.replace('"', '')), header=1)
    df = df.dropna(how='all', axis=1).dropna(how='any', axis=0)
    df.columns = [c.strip() for c in df.columns]
    df = df[df['證券代號'] == stock_id]
    if not df.empty and '千張大戶持股比率(%)' in df.columns:
        return float(df.iloc[0]['千張大戶持股比率(%)'])
    return None

def fetch_thousand_ratios(stock_id, days=60):
    today = datetime.now()
    results = []
    for i in range(days):
        date = today - timedelta(days=i)
        if date.weekday() >= 5:
            continue  # skip weekend
        date_str = date.strftime('%Y%m%d')
        csv_text = fetch_bwibbu_csv(date_str)
        if csv_text:
            ratio = parse_thousand_ratio(csv_text, stock_id)
            if ratio is not None:
                results.append((date, ratio))
    return sorted(results)

def plot_thousand_ratios(stock_id, ratio_data):
    dates, ratios = zip(*ratio_data)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, ratios, marker='o', label='千張大戶持股比例 (%)')
    plt.title(f'{stock_id} 千張大戶持股比例趨勢')
    plt.xlabel('日期')
    plt.ylabel('持股比例 (%)')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45)
    plt.legend()
    out_path = os.path.join(OUTPUT_FOLDER, f'{stock_id}_thousand_ratio.png')
    plt.tight_layout()
    plt.savefig(out_path)
    print(f'✅ 圖表已儲存：{out_path}')
    return out_path

if __name__ == '__main__':
    stock_id = input("請輸入股票代號：")
    days = int(input("請輸入分析天數（例如 60）："))
    data = fetch_thousand_ratios(stock_id, days)
    if data:
        plot_thousand_ratios(stock_id, data)
    else:
        print("❌ 查無資料或無法取得千張比例資訊。")
