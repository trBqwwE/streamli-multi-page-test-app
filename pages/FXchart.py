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
start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=180))
end_date = st.sidebar.date_input("終了日", end_date)

if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()


# --- データ取得とエラー処理 ---
try:
    data = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1))
    
    # ★★★★★★★★★★★★★★★★ 修正箇所 ★★★★★★★★★★★★★★★★
    # yfinanceが稀に文字列を返すことがあるため、データ型を強制的に数値に変換する
    
    # 1. 対象となるカラムのデータ型を強制的に数値に変換
    #    変換できない値は NaN (Not a Number) になる (errors='coerce')
    cols_to_numeric = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in cols_to_numeric:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    # 2. NaNが含まれる行を削除する
    data.dropna(inplace=True)
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    if data.empty:
        st.warning(f"{selected_pair_name} のデータが取得できませんでした。期間や為替ペア、または日付を調整してください。")
        st.stop()

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} のチャート")
    
    # デバッグ用にデータ型情報を表示したい場合は、以下のコメントを外してください
    # st.subheader("データ型情報 (デバッグ用)")
    # st.write(data.info())
    # st.write(data.head())


    fig, _ = mpf.plot(
        data,
        type='candle',
        style='yahoo',
        title=f'{selected_pair_name} Candlestick Chart',
        ylabel='Price',
        volume=True,
        ylabel_lower='Volume',
        mav=(5, 25),
        returnfig=True
    )
    st.pyplot(fig)

    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    st.error(f"データの取得または描画中にエラーが発生しました: {e}")
