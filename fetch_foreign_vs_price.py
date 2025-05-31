#!/usr/bin/env python3
import os, io, time, requests, pandas as pd
import datetime
import matplotlib.pyplot as plt

# ─── 參數設定 ─────────────────────────────────────
STOCK_NO = "2382"
DAYS = 60
IN_CSV = "t86_2382.csv"  # 本地 T86 CSV 檔，用於取得交易日期
OUT_DIR = "output"
FIG_PATH = os.path.join(OUT_DIR, f"{STOCK_NO}_foreign_vs_price.png")

# 中文字體設定，避免亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

def get_trading_dates_from_csv(path, n):
    """從本地 CSV 的 'date' 欄擷取最近 N 個交易日。"""
    df = pd.read_csv(path)
    if 'date' not in df.columns:
        raise RuntimeError(f"CSV 欄位缺少 'date'，實際欄位: {df.columns.tolist()}")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    dates = df['date'].dt.strftime('%Y%m%d').tolist()[-n:]
    return dates

def fetch_foreign_count(dates):
    """針對每個日期呼叫 T86 JSON 介面，動態擷取外資買賣超『張數』。"""
    recs = []
    API = "https://www.twse.com.tw/fund/T86?response=json&date={}&selectType=ALL"
    for d in dates:
        try:
            j = requests.get(API.format(d), timeout=5).json()
        except Exception:
            continue
        if j.get('stat') != 'OK':
            continue
        fields = j.get('fields', [])
        data = j.get('data', [])
        if '證券代號' not in fields:
            continue
        idx_code = fields.index('證券代號')
        idx_foreign = next((i for i, col in enumerate(fields) if '外陸' in col and '買賣超' in col), None)
        if idx_foreign is None:
            print(f"⚠️ {d} 無法找到外資買賣超欄位，fields: {fields}")
            continue
        for row in data:
            code = str(row[idx_code]).strip('=" ')
            if code == STOCK_NO:
                val = int(str(row[idx_foreign]).replace(',', '').strip()) // 1000  # 轉換為張數
                recs.append({'date': pd.to_datetime(d, format='%Y%m%d'),
                             '外資買賣超張數': val})
                break
        time.sleep(0.1)
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    return df.set_index('date').sort_index()

def main():
    dates = get_trading_dates_from_csv(IN_CSV, DAYS)
    print(f"▶️ 成功取得 {len(dates)} 個交易日：{dates[0]} → {dates[-1]}")

    df_f = fetch_foreign_count(dates)
    if df_f.empty:
        raise RuntimeError("❌ 未取得任何外資買賣超資料，請檢查 JSON fields 是否有變動。")

    print("✅ 外資資料日期：", df_f.index.tolist())

    # 繪製柱狀圖
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(df_f.index, df_f['外資買賣超張數'], label='外資買賣超張數', color='blue')
    ax.set_ylabel('外資買賣超張數 (張)', color='blue')
    ax.set_title(f"{STOCK_NO} 外資買賣超張數（近 {DAYS} 交易日）")
    ax.tick_params(axis='y', labelcolor='blue')
    fig.autofmt_xdate()
    ax.legend(loc='upper right')

    os.makedirs(OUT_DIR, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ 圖表已儲存：{FIG_PATH}")

if __name__ == '__main__':
    main()