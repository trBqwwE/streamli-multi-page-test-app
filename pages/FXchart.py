import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="為替レート可視化アプリ",
    page_icon="💹",
    layout="wide"
)

st.title("💹 為替レート可視化アプリ")
st.write("Yahooファイナンスからデータを取得し、為替レートの推移をグラフで表示します。")

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
end_date = datetime.now()
start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=365))
end_date = st.sidebar.date_input("終了日", end_date)

# 日付の整合性チェック
if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()

# --- データ取得 ---
# yfinanceを使って為替データを取得
try:
    data = yf.download(ticker, start=start_date, end=end_date)

    if data.empty:
        st.warning(f"{selected_pair_name} のデータが取得できませんでした。期間や為替ペアを確認してください。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} の為替レート推移")

    # Plotlyでインタラクティブなグラフを作成
    fig = px.line(
        data,
        x=data.index,
        y='Close',
        title=f'{selected_pair_name} 終値の推移',
        labels={'Close': '終値', 'index': '日付'}
    )
    fig.update_layout(
        xaxis_title='日付',
        yaxis_title='レート',
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)

    # 取得したデータの表示
    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"データの取得中にエラーが発生しました: {e}")
