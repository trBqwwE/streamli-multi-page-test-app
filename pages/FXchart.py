import streamlit as st
import pandas as pd
import yfinance as yf
import mplfinance as mpf # mplfinanceをインポート
from datetime import datetime, timedelta

# 日本語表示は不要になるため、japanize_matplotlibとmatplotlib.pyplotは削除またはコメントアウトしてもOK
# import japanize_matplotlib
# import matplotlib.pyplot as plt

# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="為替レート ローソク足チャート",
    page_icon="🕯️",
    layout="wide"
)

st.title("🕯️ 為替レート ローソク足チャート")
st.write("Yahooファイナンスのデータに基づいたローソク足チャートです。")

# --- サイドバー (変更なし) ---
st.sidebar.header("設定")
currency_pairs = {
    "米ドル/円 (USD/JPY)": "JPY=X",
    "ユーロ/円 (EUR/JPY)": "EURJPY=X",
    "豪ドル/円 (AUD/JPY)": "AUDJPY=X",
    "ポンド/円 (GBP/JPY)": "GBPJPY=X",
    "ユーロ/米ドル (EUR/USD)": "EURUSD=X",
}
selected_pair_name = st.sidebar.selectbox("為替ペアを選択してください", list(currency_pairs.keys()))
ticker = currency_pairs[selected_pair_name]

end_date = datetime.now().date()
start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=180)) # デフォルトを180日に
end_date = st.sidebar.date_input("終了日", end_date)

if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()

# --- データ取得 (変更なし) ---
try:
    data = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1))
    if data.empty:
        st.warning(f"{selected_pair_name} のデータが取得できませんでした。期間や為替ペアを確認してください。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} のチャート")

    # --- mplfinanceでローソク足チャートを描画 ---
    # グラフのスタイル設定など
    fig, _ = mpf.plot(
        data,
        type='candle',  # ローソク足チャートを指定
        style='yahoo',  # スタイル（'charles', 'yahoo', 'blueskies'など）
        title=f'{selected_pair_name} Candlestick Chart',
        ylabel='Price',
        volume=True,  # 出来高を表示
        ylabel_lower='Volume',
        mav=(5, 25),  # 5日移動平均線と25日移動平均線を追加
        returnfig=True  # Streamlitに渡すためにFigureオブジェクトを返す
    )

    # Streamlitにグラフを表示
    st.pyplot(fig)

    # 取得したデータの表示
    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"データの取得または描画中にエラーが発生しました: {e}")
