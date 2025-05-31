# daily_foreign_analysis.py
import datetime
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from app import get_trading_days, fetch_institutional_data, fetch_price_data

def run_foreign_analysis(stock_no="2382", days=60):
    today = datetime.date.today().strftime("%Y%m%d")
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    dates = get_trading_days(days)
    df_i = fetch_institutional_data(dates, stock_no)
    df_p = fetch_price_data(dates, stock_no)
    df = df_i.join(df_p, how="inner")

    if df.empty:
        print("❌ 查無資料或網路錯誤")
        return

    fig_w = max(12, len(df)*0.24)
    fig, ax1 = plt.subplots(figsize=(fig_w, 5))
    x = list(range(len(df)))

    ax1.plot(x, df['外資'].values, label='外資', color='blue')
    ax1.plot(x, df['投信'].values, label='投信', color='orange', linestyle='--')
    ax1.plot(x, df['自營商'].values, label='自營商', color='green', linestyle=':')

    ax2 = ax1.twinx()
    ax2.plot(x, df['收盤價'].values, color='red', label='收盤價')

    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.bar(x, df['成交量'].values, color='gray', alpha=0.3, width=0.6)

    labels = [d.strftime("%m/%d") for d in df.index]
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, fontsize=8)

    lines1, lbls1 = ax1.get_legend_handles_labels()
    lines2, lbls2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1+lines2, lbls1+lbls2, loc='upper left')

    plt.title(f"{stock_no}｜法人買賣超、收盤價、成交量（近{days}交易日）")
    fig.tight_layout()

    filename = f"{stock_no}_chart_{today}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ 產圖完成：{filepath}")
    return filepath
