#!/usr/bin/env python3
import os, io, time, requests, pandas as pd
import datetime
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

# ─── 參數設定 ───────────────────────────────────
STOCK_NO = "2382"
DAYS     = 60
OUT_DIR  = "output"
FIG_PATH = os.path.join(OUT_DIR, f"{STOCK_NO}_institutions_price_volume.png")

# 中文字體設定，避免亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# 動態取得最近交易日
def get_trading_dates_api(stock_no, days):
    dates = []
    today = datetime.date.today()
    offset = 0
    while len(dates) < days:
        d = today - datetime.timedelta(days=offset)
        offset += 1
        if d.weekday() >= 5:
            continue
        url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv"
               f"&date={d.strftime('%Y%m%d')}&stockNo={stock_no}")
        try:
            r = requests.get(url, timeout=5)
        except:
            continue
        if '日期' in r.text:
            dates.append(d)
    return sorted(dates)

# 抓取三大法人買賣超
def fetch_institutional(dates):
    recs = []
    API = "https://www.twse.com.tw/fund/T86?response=json&date={}&selectType=ALL"
    for d in dates:
        ds = d.strftime('%Y%m%d')
        try:
            j = requests.get(API.format(ds), timeout=5).json()
        except:
            continue
        if j.get('stat') != 'OK':
            continue
        fields, data = j['fields'], j['data']
        if '證券代號' not in fields:
            continue
        idx = fields.index('證券代號')
        for row in data:
            if str(row[idx]).strip('=" ') == STOCK_NO:
                recs.append({'date': d,
                             '外資': int(str(row[fields.index('外陸資買賣超股數(不含外資自營商)')]).replace(',', '')),
                             '投信': int(str(row[fields.index('投信買賣超股數')]).replace(',', '')),
                             '自營商': int(str(row[fields.index('自營商買賣超股數')]).replace(',', ''))})
                break
        time.sleep(0.1)
    df = pd.DataFrame(recs)
    return df.set_index('date').sort_index() if not df.empty else df

# 抓取收盤價與成交量
def fetch_price_volume(dates):
    recs = []
    for d in dates:
        ds = d.strftime('%Y%m%d')
        url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv"
               f"&date={ds}&stockNo={STOCK_NO}")
        try:
            raw = requests.get(url, timeout=5).text
            lines = raw.splitlines()
            idx = next(i for i, ln in enumerate(lines) if '日期' in ln)
            dfm = pd.read_csv(io.StringIO('\n'.join(lines[idx:])), encoding='big5')
        except:
            continue
        dfm.columns = [c.strip() for c in dfm.columns]
        dfm = dfm[dfm['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$')]
        ymd = dfm['日期'].str.split('/', expand=True).astype(int)
        dfm['date'] = [datetime.date(y+1911, mo, d) for y, mo, d in zip(ymd[0], ymd[1], ymd[2])]
        dfm['收盤價'] = pd.to_numeric(dfm['收盤價'].astype(str).str.replace(',', ''), errors='coerce')
        dfm['成交量'] = pd.to_numeric(dfm['成交股數'].astype(str).str.replace(',', ''), errors='coerce')
        recs.append(dfm[['date','收盤價','成交量']])
        time.sleep(0.1)
    if recs:
        dfpv = pd.concat(recs).drop_duplicates('date')
        return dfpv.set_index('date').sort_index()
    return pd.DataFrame()

if __name__ == '__main__':
    dates = get_trading_dates_api(STOCK_NO, DAYS)
    df_i = fetch_institutional(dates)
    df_pv = fetch_price_volume(dates)
    df_all = df_i.join(df_pv, how='inner')

    # 標記大戶 (>400 張) 事件
    big = df_i[(df_i['外資'].abs()>400) | (df_i['投信'].abs()>400) | (df_i['自營商'].abs()>400)]

    # 繪圖
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df_all.index, df_all['外資'],   label='外資 (張)',   color='blue',  lw=2)
    ax1.plot(df_all.index, df_all['投信'],   label='投信 (張)',   color='orange', lw=2, ls='--')
    ax1.plot(df_all.index, df_all['自營商'], label='自營商 (張)', color='green',  lw=2, ls='-.')
    # 大戶標記
    ax1.scatter(big.index, big['外資'],   color='blue',  edgecolor='black', s=50, marker='o', label='外資>400')
    ax1.scatter(big.index, big['投信'],   color='orange',edgecolor='black', s=50, marker='s', label='投信>400')
    ax1.scatter(big.index, big['自營商'], color='green', edgecolor='black', s=50, marker='^', label='自營商>400')
    ax1.set_ylabel('法人買賣超 (張)')
    ax1.grid(True, linestyle='--', alpha=0.3)

    # 收盤價
    ax2 = ax1.twinx()
    ax2.plot(df_all.index, df_all['收盤價'], label='收盤價 (NT$)', color='red', lw=2)
    ax2.set_ylabel('收盤價 (NT$)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    # 成交量
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.bar(df_all.index, df_all['成交量'], label='成交量 (張)', color='gray', alpha=0.3)
    ax3.set_ylabel('成交量 (張)', color='gray')
    ax3.tick_params(axis='y', labelcolor='gray')

    # X 軸全部刻度
    ax1.set_xticks(df_all.index)
    ax1.set_xticklabels([d.strftime('%m/%d') for d in df_all.index], rotation=45, ha='right')

    # 圖例
    handles, labels = [], []
    for ax in (ax1, ax2, ax3):
        h, l = ax.get_legend_handles_labels()
        handles += h; labels += l
    ax1.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=6, fontsize='small')

    plt.title(f"{STOCK_NO} 三大法人買賣超、收盤價與成交量（近{DAYS}交易日）", fontsize=14)
    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=300)
    plt.close(fig)
    print(f"✅ 圖表已儲存：{FIG_PATH}")
