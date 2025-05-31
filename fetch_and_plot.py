#!/usr/bin/env python3
import os, io, time, requests, pandas as pd, datetime
import matplotlib.pyplot as plt

# ─── 參數設定 ─────────────────────────────────────
STOCK_NO = "2382"
DAYS = 60
OUT_DIR = "output"
FIG_PATH = os.path.join(OUT_DIR, f"{STOCK_NO}_holdings_price.png")

# 中文字體設定，避免亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False


def get_trading_dates(days):
    """從台灣證交所 STCOK_DAY CSV 擷取最近 N 個交易日日期。"""
    today = datetime.datetime.today()
    # 取每月第一天，TWSE 回傳整月所有交易日
    first_day = today.replace(day=1)
    date_param = first_day.strftime("%Y%m%d")
    url = (
        f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv"
        f"&date={date_param}&stockNo={STOCK_NO}"
    )
    r = requests.get(url, timeout=5)
    r.encoding = 'cp950'
    lines = r.text.splitlines()
    # 找到含 "日期" 的欄位行索引
    header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith('日期')), None)
    if header_idx is None:
        raise RuntimeError("⚠️ 無法從回傳內容中找到交易日表頭，請檢查 URL 或網路狀況。")
    csv_text = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_text))
    df = df.dropna(how='all')
    df['日期'] = pd.to_datetime(df['日期'], format='%Y/%m/%d')
    # 最後 N 筆交易日
    dates = df['日期'].dt.strftime('%Y%m%d').tolist()[-days:]
    return dates


def fetch_ratios(dates):
    """針對每個日期呼叫 JSON 介面，擷取三大法人持股比率。"""
    recs = []
    for dt in dates:
        url = (
            f"https://www.twse.com.tw/fund/TWT38U?response=json"
            f"&date={dt}&selectType=ALLBUT0999"
        )
        try:
            j = requests.get(url, timeout=5).json()
        except Exception:
            continue
        if j.get('stat') != 'OK':
            continue
        fields = j.get('fields', [])
        data = j.get('data', [])
        if '證券代號' not in fields:
            print(f"⚠️ {dt} 表頭缺少 '證券代號'，實際 fields: {fields}")
            continue
        idx_id = fields.index('證券代號')
        idx_f  = fields.index('全體外資及陸資持股比率(%)')
        idx_i  = fields.index('投信持股比率(%)')
        idx_d  = fields.index('自營商持股比率(%)')
        for row in data:
            code = str(row[idx_id]).strip('=" ')
            if code == STOCK_NO:
                recs.append({
                    'date': pd.to_datetime(dt, format='%Y%m%d'),
                    '外資持股比率': float(row[idx_f]),
                    '投信持股比率': float(row[idx_i]),
                    '自營商持股比率': float(row[idx_d]),
                })
                break
        time.sleep(0.1)
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    return df.sort_values('date').set_index('date')


def fetch_prices(dates):
    """下載每日收盤價，逐日呼叫 CSV 介面。"""
    recs = []
    for dt in dates:
        url = (
            f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv"
            f"&date={dt}&stockNo={STOCK_NO}"
        )
        r = requests.get(url, timeout=5)
        r.encoding = 'cp950'
        lines = r.text.splitlines()
        header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith('日期')), None)
        if header_idx is None:
            continue
        csv_text = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_text))
        df = df.dropna(how='all')
        df['日期'] = pd.to_datetime(df['日期'], format='%Y/%m/%d')
        df['收盤價'] = df['收盤價'].astype(str).str.replace(',', '').astype(float)
        recs.append({'date': df['日期'].iloc[0], '收盤價': df['收盤價'].iloc[0]})
        time.sleep(0.1)
    dfp = pd.DataFrame(recs)
    if dfp.empty:
        return dfp
    return dfp.sort_values('date').set_index('date')


def main():
    dates = get_trading_dates(DAYS)
    df_r = fetch_ratios(dates)
    if df_r.empty:
        raise RuntimeError("❌ 沒有取得任何法人持股比率資料，請檢查 API fields 是否正確。")
    df_p = fetch_prices(dates)
    df = df_r.join(df_p, how='inner')
    if df.empty:
        raise RuntimeError("❌ 合併後沒有共同日期資料，請確認日期和 API 資料對應。")

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df.index, df['外資持股比率'], label='外資持股比率', linewidth=2)
    ax1.plot(df.index, df['投信持股比率'], label='投信持股比率', linewidth=2)
    ax1.plot(df.index, df['自營商持股比率'], label='自營商持股比率', linewidth=2)
    ax1.set_ylabel('持股比率 (%)')
    ax1.legend(loc='upper left')

    ax2 = ax1.twinx()
    ax2.plot(df.index, df['收盤價'], label='收盤價', color='black', linestyle='--')
    ax2.set_ylabel('收盤價 (元)')
    ax2.legend(loc='upper right')

    plt.title(f"{STOCK_NO} 三大法人持股比率與收盤價")
    fig.autofmt_xdate()

    os.makedirs(OUT_DIR, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表已儲存：{FIG_PATH}")

if __name__ == '__main__':
    main()
