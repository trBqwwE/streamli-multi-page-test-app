import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np # pandasやmatplotlibの内部でよく使われます
from datetime import datetime, timedelta
import japanize_matplotlib
# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="為替レート可視化アプリ (Matplotlib版)",
    page_icon="💹",
    layout="wide"
)

st.title("💹 為替レート可視化アプリ (Matplotlib版)")
st.write("Yahooファイナンスからデータを取得し、matplotlibを使って為替レートの推移をグラフで表示します。")

# --- サイドバーの設定 ---
st.sidebar.header("設定")

# 為替ペアの選択
# Yahoo Financeでは、例えばUSD/JPYは "JPY=X" のように表現されます。
currency_pairs = {
    "米ドル/円 (USD/JPY)": "JPY=X",
    "ユーロ/円 (EUR/JPY)": "EURJPY=X",
    "豪ドル/円 (AUD/JPY)": "AUDJPY=X",
    "ポンド/円 (GBP/JPY)": "GBPJPY=X",
    "ユーロ/米ドル (EUR/USD)": "EURUSD=X",
}
selected_pair_name = st.sidebar.selectbox("為替ペアを選択してください", list(currency_pairs.keys()))
ticker = currency_pairs[selected_pair_name]

# 期間の選択
end_date = datetime.now().date() # .date() をつけて日付オブジェクトに
start_date_default = end_date - timedelta(days=365)
start_date = st.sidebar.date_input("開始日", start_date_default)
end_date = st.sidebar.date_input("終了日", end_date)

# 日付の整合性チェック
if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()

# --- データ取得 ---
# yfinanceを使って為替データを取得
try:
    # 終了日を翌日に設定して、当日分のデータを取得できるようにする
    data = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1))

    if data.empty:
        st.warning(f"{selected_pair_name} のデータが取得できませんでした。期間や為替ペアを確認してください。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} の為替レート推移")

    # Matplotlibでグラフを作成
    # FigureとAxesオブジェクトを作成
    fig, ax = plt.subplots(figsize=(12, 6))

    # データをプロット
    ax.plot(data.index, data['Close'], label='終値', color='royalblue')

    # グラフのタイトルとラベルを設定
    ax.set_title(f'{selected_pair_name} 終値の推移', fontsize=16)
    ax.set_xlabel('日付', fontsize=12)
    ax.set_ylabel('レート', fontsize=12)

    # グリッド線を表示
    ax.grid(True, linestyle='--', alpha=0.6)

    # 凡例を表示
    ax.legend()

    # X軸の日付ラベルが見やすくなるように自動で回転させる
    fig.autofmt_xdate()

    # Streamlitにグラフを表示
    st.pyplot(fig)


    # 取得したデータの表示
    st.subheader("取得データ")
    # 小数点以下4桁で表示するようにスタイルを設定
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"データの取得または描画中にエラーが発生しました: {e}")
