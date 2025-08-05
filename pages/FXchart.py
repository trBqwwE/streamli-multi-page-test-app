import streamlit as st
import pandas as pd
import yfinance as yf
import mplfinance as mpf
from datetime import datetime, timedelta

# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="為替レート ローソク足チャート",
    page_icon="🕯️",
    layout="wide"
)

st.title("🕯️ 為替レート ローソク足チャート")
st.write("Yahooファイナンスのデータに基づいたローソク足チャートです。")

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
    # 1. auto_adjust=False を指定
    raw_data = yf.download(
        ticker,
        start=start_date,
        end=end_date + timedelta(days=1),
        auto_adjust=False
    )

    if raw_data.empty:
        st.warning(f"指定された期間にデータが存在しません。")
        st.stop()

    # ★★★★★★★★★★★★★★★★★★★ 最終修正箇所 ★★★★★★★★★★★★★★★★★★★
    # --- データフレームの完全再構築 ---
    # 2. 必要なカラムだけを明示的に抽出
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = raw_data[required_columns].copy()

    # 3. インデックスを強制的に日付型に変換
    data.index = pd.to_datetime(data.index)

    # 4. 各列を強制的に数値型に変換
    for col in required_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    # 5. 不正な行を削除
    data.dropna(inplace=True)
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    if data.empty:
        st.warning(f"指定された期間に有効なデータが存在しませんでした（市場の休日など）。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} のチャート")

    # データ件数に応じて移動平均線の表示を制御
    mav_options = []
    if len(data) >= 5:
        mav_options.append(5)
    if len(data) >= 25:
        mav_options.append(25)

    # mplfinanceで描画
    fig, _ = mpf.plot(
        data,
        type='candle',
        style='yahoo',
        title=f'{selected_pair_name} Candlestick Chart',
        ylabel='Price',
        volume=True,
        ylabel_lower='Volume',
        mav=mav_options if mav_options else None, # 件数が足りない場合はMAを表示しない
        returnfig=True
    )

    if fig:
        st.pyplot(fig)
    else:
        st.error("チャートの描画に失敗しました。")

    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"処理中に予期せぬエラーが発生しました: {e}")
