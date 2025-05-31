import requests
import pandas as pd
import io
from datetime import datetime, timedelta

def fetch_bwibbu_thousand_ratio(target_stock_id, days=30):
    today = datetime.today()
    result = []

    for i in range(days):
        date = (today - timedelta(days=i))
        yyyymmdd = date.strftime('%Y%m%d')
        url = f"https://www.twse.com.tw/fund/BWIBBU_d?response=csv&date={yyyymmdd}&selectType=ALL"
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            csv_text = response.text

            # 清理前綴亂碼與空白行
            lines = csv_text.splitlines()
            clean_lines = [line for line in lines if line.count(',') > 10]
            if not clean_lines:
                print(f"❌ {yyyymmdd} 無有效資料")
                continue

            cleaned_csv = '\n'.join(clean_lines)
            df = pd.read_csv(io.StringIO(cleaned_csv))

            df = df.dropna(how='all')
            df.columns = df.columns.str.strip()  # 去除欄位空白

            # 若欄位名稱不同，也允許匹配英文欄位或備選欄位
            possible_columns = [col for col in df.columns if '千張' in col and '比例' in col]
            if not possible_columns:
                print(f"⚠️ {yyyymmdd} 無法判斷千張持股欄位")
                continue

            target_column = possible_columns[0]  # 取第一個匹配欄位
            df['證券代號'] = df['證券代號'].astype(str).str.strip()
            row = df[df['證券代號'] == str(target_stock_id)]
            if not row.empty:
                ratio = row.iloc[0][target_column]
                result.append({'date': yyyymmdd, 'ratio': float(ratio)})
            else:
                print(f"⚠️ {yyyymmdd} 找不到股票 {target_stock_id} 的資料")

        except Exception as e:
            print(f"❌ {yyyymmdd} 抓取失敗: {e}")

    return pd.DataFrame(result)

if __name__ == '__main__':
    stock_id = input("請輸入股票代號（如 2382）：")
    days = int(input("請輸入要查詢的天數（如 30）："))
    df = fetch_bwibbu_thousand_ratio(stock_id, days)
    if df.empty:
        print("未取得任何千張大戶資料")
    else:
        print("✅ 成功取得資料：")
        print(df)
        df.to_csv(f"{stock_id}_thousand_ratio.csv", index=False, encoding='utf-8-sig')