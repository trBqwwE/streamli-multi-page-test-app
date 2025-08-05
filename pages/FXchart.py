import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="為替レート ローソク足チャート (Plotly版)",
    page_icon="✨",
    layout="wide"
)

st.title("✨ 為替レート ローソク足チャート (Plotly版)")
st.write("Yahooファイナンスのデータに基づいた、インタラクティブなチャートです。")

# --- サイドバー ---
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
start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=180))
end_date = st.sidebar.date_input("終了日", end_date)

if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()


# --- データ取得とエラー処理 ---
try:
    # 1. auto_adjust=False を指定して、'Open', 'High', 'Low', 'Close' 列を確実に取得
    raw_data = yf.download(
        ticker,
        start=start_date,
        end=end_date + timedelta(days=1),
        auto_adjust=False,
        progress=False # ダウンロードの進捗表示をオフに
    )

    if raw_data.empty:
        st.warning(f"指定された期間にデータが存在しません。")
        st.stop()

    # 2. 必要なカラムだけを明示的に抽出し、データ型を保証する
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = raw_data[required_columns].copy()
    for col in required_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    # 3. 不正な行を削除
    data.dropna(inplace=True)

    if data.empty:
        st.warning(f"指定された期間に有効なデータが存在しませんでした（市場の休日など）。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} のチャート")

    # 4. Plotlyでローソク足チャートを作成
    fig = go.Figure()

    # ローソク足の追加
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='ローソク足'
    ))

    # 5日移動平均線の追加
    if len(data) >= 5:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['Close'].rolling(window=5).mean(),
            mode='lines', name='MA5 (5日移動平均線)',
            line=dict(color='orange', width=1)
        ))

    # 25日移動平均線の追加
    if len(data) >= 25:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['Close'].rolling(window=25).mean(),
            mode='lines', name='MA25 (25日移動平均線)',
            line=dict(color='purple', width=1)
        ))
    
    # グラフのレイアウト設定
    fig.update_layout(
        title_text=f'{selected_pair_name} 価格推移',
        xaxis_title='日付',
        yaxis_title='価格',
        xaxis_rangeslider_visible=False, # 下部のレンジスライダーを非表示に
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # 凡例をグラフ上部に表示
    )

    # Streamlitにグラフを表示
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"処理中に予期せぬエラーが発生しました: {e}")
