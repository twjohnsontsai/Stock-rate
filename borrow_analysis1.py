# borrow_analysis1.py

import sys
import pandas as pd
import matplotlib.pyplot as plt
import os
import requests
import io
from datetime import datetime, timedelta
import matplotlib.ticker as mticker
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

DATA_FOLDER = './data/twt93u/'
OUTPUT_FOLDER = './output/'
BORROW_URL = 'https://www.twse.com.tw/exchangeReport/TWT93U?response=csv&date={date}'
PRICE_URL = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={date}&stockNo={stock}'

def get_available_days(n):
    os.makedirs(DATA_FOLDER, exist_ok=True)
    days = []
    today = datetime.today()
    count = 0
    max_lookback = 150

    while count < n and max_lookback > 0:
        if today.weekday() < 5:
            d = today.strftime('%Y%m%d')
            file_path = os.path.join(DATA_FOLDER, f'TWT93U_{d}.csv')
            if download_csv(BORROW_URL.format(date=d), file_path):
                if os.path.getsize(file_path) > 0:
                    days.append(d)
                    count += 1
        today -= timedelta(days=1)
        max_lookback -= 1

    return sorted(days)

def download_csv(url, path):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return True
        return False
    except:
        return False

def read_borrow_data(dates):
    records = []
    for d in dates:
        f = os.path.join(DATA_FOLDER, f'TWT93U_{d}.csv')
        if not os.path.exists(f) or os.path.getsize(f) == 0:
            continue
        try:
            df = pd.read_csv(f, encoding='cp950', header=1).iloc[1:, :15]
            df.columns = ['代號', '名稱', '融券前日', '融券賣出', '融券買進', '融券現券',
                          '融券今日餘額', '融券次限額', '借券前日', '借券賣出', '借券還券',
                          '借券調整', '借券餘額', '借券次限額', '備註']
            df['代號'] = df['代號'].astype(str).str.extract(r'(\d+)')[0]
            for c in ['借券前日', '借券賣出', '借券還券', '借券餘額']:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')
            date_val = datetime.strptime(d, '%Y%m%d').date()
            for _, row in df.iterrows():
                records.append({
                    '日期': date_val,
                    '代號': row['代號'],
                    '借券賣出': row['借券賣出'],
                    '借券還券': row['借券還券'],
                    '借券餘額': row['借券餘額'],
                })
        except:
            continue
    return pd.DataFrame(records)

def read_price_data(stock, dates):
    months = sorted({(int(d[:4]), int(d[4:6])) for d in dates})
    frames = []
    for y, m in months:
        try:
            url = PRICE_URL.format(date=f"{y}{m:02d}01", stock=stock)
            content = requests.get(url).content.decode('big5')
            dfm = pd.read_csv(io.StringIO(content), skiprows=1, encoding='big5')
        except:
            continue
        dfm.columns = [c.strip() for c in dfm.columns]
        dfm = dfm[dfm['日期'].astype(str).str.match(r'^\d{3}/\d{1,2}/\d{1,2}$')]
        ymd = dfm['日期'].str.split('/', expand=True).astype(int)
        dfm['日期'] = [datetime(y + 1911, mo, d).date() for y, mo, d in zip(ymd[0], ymd[1], ymd[2])]
        dfm['收盤價'] = pd.to_numeric(dfm['收盤價'], errors='coerce')
        dfm['成交量'] = pd.to_numeric(dfm['成交股數'].str.replace(',', ''), errors='coerce')
        frames.append(dfm[['日期', '收盤價', '成交量']])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).drop_duplicates('日期').sort_values('日期').reset_index(drop=True)

def plot_borrow_chart(stock, float_shares, days):
    days_list = get_available_days(days)
    borrow_df = read_borrow_data(days_list)
    price_df = read_price_data(stock, days_list)

    df = price_df.copy()
    borrow = borrow_df[borrow_df['代號'] == stock][['日期', '借券賣出', '借券還券', '借券餘額']]
    df = df.merge(borrow, how='left', on='日期')
    df[['借券賣出', '借券還券']] = df[['借券賣出', '借券還券']].fillna(0)
    df['借券餘額'] = df['借券餘額'].ffill().bfill()
    df[['借券賣出', '借券還券', '借券餘額', '成交量']] /= 1000

    x = np.arange(len(df))
    fig, ax1 = plt.subplots(figsize=(max(12, len(df) * 0.22), 6))
    ax1.bar(x, df['借券賣出'], label='借券賣出', alpha=0.6)
    ax1.bar(x, -df['借券還券'], label='借券還券', alpha=0.6)
    ax1.plot(x, df['借券餘額'], label='借券餘額', marker='o')
    ax1.set_ylabel('借券張數 (千張)')
    ax1.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))

    ax2 = ax1.twinx()
    ax2.plot(x, df['收盤價'], label='收盤價', linestyle='--', marker='s', color='red')
    ax2.set_ylabel('收盤價 (NT$)')
    ax2.tick_params(axis='y', labelcolor='red')

    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.bar(x, df['成交量'], label='成交量', alpha=0.3, color='tab:green')
    ax3.set_ylabel('成交量 (千張)')
    ax3.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))

    labels = [f"{d.month}/{d.day}" for d in df['日期']]
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, fontsize=max(6, int(1000 / max(12, len(df) * 0.22))))
    ax1.set_xlim(-0.5, len(x) - 0.5)

    rates = (df['成交量'] / (float_shares / 1000) * 100).round(2)
    ax1.text(x[0], -0.12, '換手率 (%)', transform=ax1.get_xaxis_transform(), ha='left')
    for xi, rt in zip(x, rates):
        color = 'red' if rt > 1.5 else 'black'
        ax1.text(xi, -0.15, f"{rt:.2f}%", transform=ax1.get_xaxis_transform(),
                 ha='center', va='top', color=color, rotation=90, fontsize=8)

    handles, labels = [], []
    for ax in [ax1, ax2, ax3]:
        h, l = ax.get_legend_handles_labels()
        handles += h
        labels += l

    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.94), ncol=4)
    plt.title(f"{stock} 借券與股價成交分析 (近 {days} 交易日)")
    plt.subplots_adjust(bottom=0.25, top=0.9)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    fname = f"{stock}_borrow_analysis_{datetime.today().strftime('%Y%m%d')}.png"
    plt.savefig(os.path.join(OUTPUT_FOLDER, fname), dpi=150, bbox_inches='tight')
    plt.close()
    return fname
    __all__ = [
        'get_available_days',
        'read_borrow_data',
        'read_price_data',
        'plot_borrow_chart',
        'plot_institution_chart'
    ] 

