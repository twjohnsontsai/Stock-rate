#!/usr/bin/env python3
import os, io, time, requests, pandas as pd
import datetime
import matplotlib.pyplot as plt

# ─── 參數設定 ───────────────────────────────────
STOCK_NO = input("請輸入股票代號（如1301）：").strip()

DAYS     = 60
OUT_DIR  = "output"
# 在檔名加入執行日期，避免覆蓋
TODAY    = datetime.date.today().strftime('%Y%m%d')
FIG_PATH = os.path.join(OUT_DIR, f"{STOCK_NO}_institutions_and_price_{TODAY}.png")

# 中文字體設定，避免亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# 取得最近 N 個交易日 (跳過週末)
def get_trading_days(n):
    days = []
    dt = datetime.date.today()
    while len(days) < n:
        if dt.weekday() < 5:  # Mon-Fri
            days.append(dt.strftime('%Y%m%d'))
        dt -= datetime.timedelta(days=1)
    return list(reversed(days))

# 抓取三大法人買賣超 (張)
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

# 抓取收盤價與成交量 (張)
def fetch_price_data(dates):
    dt_idx = pd.to_datetime(dates, format='%Y%m%d')
    months = sorted({d.strftime('%Y%m01') for d in dt_idx})
    records = []
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={m}&stockNo={STOCK_NO}"
        try:
            raw = requests.get(url, timeout=5).text
            lines = raw.splitlines()
            header = next(i for i, ln in enumerate(lines) if '日期' in ln)
            dfm = pd.read_csv(io.StringIO('\n'.join(lines[header:])), encoding='big5')
        except:
            continue
        dfm.columns = [c.strip() for c in dfm.columns]
        dfm = dfm[dfm['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$', na=False)]
        ymd = dfm['日期'].str.split('/', expand=True).astype(int)
        dfm['date'] = [datetime.date(y+1911, mo, d) for y, mo, d in zip(ymd[0], ymd[1], ymd[2])]
        dfm['收盤價'] = pd.to_numeric(dfm['收盤價'].astype(str).str.replace(',', ''), errors='coerce')
        dfm['成交量'] = pd.to_numeric(dfm['成交股數'].astype(str).str.replace(',', ''), errors='coerce') // 1000
        records.append(dfm[['date','收盤價','成交量']])
        time.sleep(0.1)
    if records:
        dfp = pd.concat(records).drop_duplicates('date').set_index('date').sort_index()
        return dfp
    return pd.DataFrame()

# 主程式入口
if __name__ == '__main__':
    dates = get_trading_days(DAYS)
    print(f"▶️ 最近交易日：{dates[0]} → {dates[-1]} 共 {len(dates)} 筆")

    df_i = fetch_institutional_counts(dates)
    if df_i.empty:
        raise RuntimeError("❌ 無法人資料")

    df_p = fetch_price_data(df_i.index.strftime('%Y%m%d').tolist())
    if df_p.empty:
        raise RuntimeError("❌ 無股價資料")

    df = df_i.join(df_p, how='inner')
    if df.empty:
        raise RuntimeError("❌ 合併後無共同日期資料")

    # 繪圖
    x = list(range(len(df)))
    fig, ax1 = plt.subplots(figsize=(12,6))
    ax1.plot(x, df['外資'],   label='外資 (張)',   color='blue',  lw=2)
    ax1.plot(x, df['投信'],   label='投信 (張)',   color='orange', lw=2, ls='--')
    ax1.plot(x, df['自營商'], label='自營商 (張)', color='green',  lw=2, ls='-.')
    ax1.set_ylabel('法人買賣超 (張)')
    ax1.grid(True, ls='--', alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, df['收盤價'], label='收盤價 (NT$)', color='red', lw=2)
    ax2.set_ylabel('收盤價 (NT$)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.bar(x, df['成交量'], label='成交量 (張)', color='gray', alpha=0.3)
    ax3.set_ylabel('成交量 (張)', color='gray')
    ax3.tick_params(axis='y', labelcolor='gray')

    ax1.set_xticks(x)
    ax1.set_xticklabels([d.strftime('%m/%d') for d in df.index], rotation=45)

    # 圖例放內部上方
    handles, labels = [], []
    for ax in (ax1, ax2, ax3):
        h, l = ax.get_legend_handles_labels()
        handles += h; labels += l
    ax1.legend(handles, labels, loc='upper center', ncol=5, fontsize='small')

    plt.title(f"{STOCK_NO} 三大法人、收盤價與成交量（近{DAYS}交易日）")
    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=300, bbox_inches='tight')
    print(f"✅ 圖表已儲存：{FIG_PATH}")
