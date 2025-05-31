#!/usr/bin/env python3
import os, io, time, requests, pandas as pd
import datetime
import matplotlib.pyplot as plt

# ─── 參數設定 ───────────────────────────────────
STOCK_NO = "2382"
DAYS = 60
IN_CSV = "t86_2382.csv"  # 本地 T86 CSV 檔，用於取得交易日期
OUT_DIR = "output"
FIG_PATH = os.path.join(OUT_DIR, f"{STOCK_NO}_institutions_and_price.png")

# 中文字體設定，避免亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

def get_trading_dates_from_csv(path, n):
    df = pd.read_csv(path)
    if 'date' not in df.columns:
        raise RuntimeError(f"CSV 欄位缺少 'date'，實際欄位: {df.columns.tolist()}")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    return df['date'].dt.strftime('%Y%m%d').tolist()[-n:]

def fetch_institutional_counts(dates):
    recs = []
    API = "https://www.twse.com.tw/fund/T86?response=json&date={}&selectType=ALL"
    for d in dates:
        try:
            j = requests.get(API.format(d), timeout=5).json()
        except:
            continue
        if j.get('stat') != 'OK':
            continue
        fields, data = j.get('fields', []), j.get('data', [])
        if '證券代號' not in fields:
            continue
        idx = fields.index('證券代號')
        try:
            f_idx = fields.index('外陸資買賣超股數(不含外資自營商)')
            i_idx = fields.index('投信買賣超股數')
            d_idx = fields.index('自營商買賣超股數')
        except ValueError:
            print(f"⚠️ {d} 欄位傳回錯誤：{fields}")
            continue
        for row in data:
            if str(row[idx]).strip('=" ') == STOCK_NO:
                recs.append({
                    'date': pd.to_datetime(d, format='%Y%m%d'),
                    '外資': int(str(row[f_idx]).replace(',', '')) // 1000,
                    '投信': int(str(row[i_idx]).replace(',', '')) // 1000,
                    '自營商': int(str(row[d_idx]).replace(',', '')) // 1000
                })
                break
        time.sleep(0.1)
    df = pd.DataFrame(recs)
    return df.set_index('date').sort_index() if not df.empty else df

def fetch_price_data(dates):
    # 只針對有法人資料的日期抓取股價
    dt_idx = pd.to_datetime(dates, format='%Y%m%d')
    months = sorted({d.strftime('%Y%m01') for d in dt_idx})
    print(f"🔍 實際所需月份：{months}")
    records = []
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={m}&stockNo={STOCK_NO}"
        try:
            raw = requests.get(url, timeout=5).text
            lines = raw.splitlines()
            header_idx = next(i for i, ln in enumerate(lines) if '日期' in ln)
            csv_text = '\n'.join(lines[header_idx:])
            df = pd.read_csv(io.StringIO(csv_text), encoding='big5')
            df.columns = [str(c).strip() for c in df.columns]
            df = df[[ '日期', '收盤價', '成交股數' ]]
            df = df[df['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$', na=False)]
            ymd = df['日期'].str.split('/', expand=True).astype(int)
            df['date'] = [datetime.date(y+1911, mo, d) for y, mo, d in zip(ymd[0], ymd[1], ymd[2])]
            df['收盤價'] = pd.to_numeric(df['收盤價'].astype(str).str.replace(',', ''), errors='coerce')
            df['成交量'] = pd.to_numeric(df['成交股數'].astype(str).str.replace(',', ''), errors='coerce') // 1000
            records.append(df[['date','收盤價','成交量']])
        except Exception as e:
            print(f"⚠️ {m} 發生錯誤：{e}")
        time.sleep(0.1)
    if records:
        df_all = pd.concat(records).drop_duplicates('date').set_index('date').sort_index()
        print("📆 收盤價資料日期：", df_all.index.tolist())
        return df_all
    return pd.DataFrame()

def main():
    dates = get_trading_dates_from_csv(IN_CSV, DAYS)
    print(f"▶️ 成功取得 {len(dates)} 個交易日：{dates[0]} → {dates[-1]}")

    df_i = fetch_institutional_counts(dates)
    if df_i.empty:
        raise RuntimeError("❌ 未取得任何法人買賣超資料，請檢查 JSON fields 是否有變動。")

    df_p = fetch_price_data(df_i.index.strftime('%Y%m%d').tolist())
    if df_p.empty:
        raise RuntimeError("❌ 未取得任何收盤價資料，請檢查 TWSE 股票日資料來源。")

    df = df_i.join(df_p, how='inner')
    if df.empty:
        raise RuntimeError("❌ 合併後沒有共同日期資料。")

    print("✅ 合併資料日期：", df.index.tolist())

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df.index, df['外資'], label='外資', linewidth=2)
    ax1.plot(df.index, df['投信'], label='投信', linestyle='--', linewidth=2)
    ax1.plot(df.index, df['自營商'], label='自營商', linestyle='-.', linewidth=2)
    ax1.set_ylabel('法人買賣超（張）')

    ax2 = ax1.twinx()
    ax2.plot(df.index, df['收盤價'], label='收盤價', color='orange', linewidth=2)
    ax2.plot(df.index, df['成交量'], label='成交量（千張）', color='gray', linestyle=':', linewidth=1.5)
    ax2.set_ylabel('收盤價／成交量')

    ax1.set_xticks(df.index)
    ax1.set_xticklabels([d.strftime('%m/%d') for d in df.index], rotation=45)

    lines, labels = ax1.get_legend_handles_labels()
    l2, lbl2 = ax2.get_legend_handles_labels()
    fig.legend(lines + l2, labels + lbl2, loc='upper center', ncol=4)

    ax1.set_title(f"{STOCK_NO} 三大法人買賣超、收盤價與成交量（近 {DAYS} 交易日）")
    ax1.grid(True, linestyle='--', alpha=0.5)

    os.makedirs(OUT_DIR, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ 圖表已儲存：{FIG_PATH}")

if __name__ == '__main__':
    main()