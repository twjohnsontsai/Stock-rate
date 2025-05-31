#!/usr/bin/env python3
import os
import io
import time
import requests
import pandas as pd
import datetime
import matplotlib.pyplot as plt

# ─── 參數設定 ───────────────────────────────────
IN_CSV = "t86_2382.csv"   # 本地 T86 CSV 檔
DAYS   = 60
STOCK_NO = "2382"

# 1. 讀取交易日 (從本地 CSV)
def get_trading_dates_from_csv(path, n):
    df = pd.read_csv(path)
    if 'date' not in df.columns:
        raise RuntimeError(f"CSV 欄位缺少 'date'，實際欄位: {df.columns.tolist()}")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    return df['date'].dt.strftime('%Y%m%d').tolist()[-n:]

# 2. 抓取收盤價與成交量 (張)
def fetch_price_data(dates):
    dt_idx = pd.to_datetime(dates, format='%Y%m%d')
    months = sorted({d.strftime('%Y%m01') for d in dt_idx})
    records = []
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={m}&stockNo={STOCK_NO}"
        try:
            raw = requests.get(url, timeout=5).text
            lines = raw.splitlines()
            idx = next(i for i, ln in enumerate(lines) if '日期' in ln)
            csv_text = '\n'.join(lines[idx:])
            df = pd.read_csv(io.StringIO(csv_text), encoding='big5')
            df.columns = [c.strip() for c in df.columns]
            df = df[['日期','成交股數']]
            df = df[df['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$', na=False)]
            ymd = df['日期'].str.split('/', expand=True).astype(int)
            df['date'] = [datetime.date(y+1911, mo, d) for y, mo, d in zip(ymd[0], ymd[1], ymd[2])]
            df['成交量'] = pd.to_numeric(df['成交股數'].astype(str).str.replace(',', ''), errors='coerce')
            records.append(df[['date','成交量']])
        except Exception as e:
            print(f"⚠️ {m} 下載失敗：{e}")
        time.sleep(0.1)
    if not records:
        return pd.DataFrame()
    df_all = pd.concat(records).drop_duplicates('date').set_index('date').sort_index()
    return df_all

# 3. 主程式：繪製成交量 > 400 張 的日期折線圖
def main():
    dates = get_trading_dates_from_csv(IN_CSV, DAYS)
    df_p = fetch_price_data(dates)
    if df_p.empty:
        raise RuntimeError("❌ 未取得任何成交量資料。")

    # 篩選：大於 400 張
    big = df_p[df_p['成交量'] > 400]
    if big.empty:
        print("⚠️ 沒有交易日成交量超過 400 張。")
        return

    # 繪圖
    plt.figure(figsize=(10, 4))
    plt.plot(big.index, big['成交量'], marker='o', linestyle='-', linewidth=2)
    plt.title('成交量 > 400 張 的交易日')
    plt.ylabel('成交量 (張)')
    plt.xticks(big.index, [d.strftime('%m/%d') for d in big.index], rotation=45)
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()
