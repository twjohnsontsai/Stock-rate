# fetch_price_test.py
import requests, io
import pandas as pd
import datetime, time

DAYS = 60  # 或其他你要的天數

STOCK_NO = "2382"

def fetch_price_data():
    today = datetime.datetime.today()
    months = sorted({(today - datetime.timedelta(days=30*i)).strftime('%Y%m01') for i in range((DAYS//20)+2)})
    dfs = []
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={m}&stockNo={STOCK_NO}"
        try:
            r = requests.get(url)
            df = pd.read_csv(io.StringIO(r.text), skiprows=1, encoding='big5')
            df = df[df.columns[:9]]
            df.columns = [c.strip() for c in df.columns]
            df['日期'] = df['日期'].astype(str)
            df = df[df['日期'].str.match(r'^\d{3}/\d+/\d+$', na=False)]
            ymd = df['日期'].str.split('/', expand=True).astype(int)
            df['date'] = [datetime.date(y+1911, m, d) for y,m,d in zip(ymd[0], ymd[1], ymd[2])]
            df['收盤價'] = pd.to_numeric(df['收盤價'].astype(str).str.replace(',',''), errors='coerce')
            df['成交量'] = pd.to_numeric(df['成交股數'].astype(str).str.replace(',',''), errors='coerce') // 1000
            dfs.append(df[['date','收盤價','成交量']])
        except Exception as e:
            print(f"⚠️ {m} 發生錯誤：", e)
        time.sleep(0.1)
    if dfs:
        return pd.concat(dfs).drop_duplicates('date').set_index('date').sort_index()
    return pd.DataFrame()


df = fetch_price_data()
print(df.tail())

