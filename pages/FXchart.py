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
    
    # データが存在する場合のみ、前処理を実行
    if not data.empty:
        # 1. 対象となるカラムのデータ型を強制的に数値に変換
        cols_to_numeric = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in cols_to_numeric:
            data[col] = pd.to_numeric(data[col], errors='coerce')

        # 2. NaNが含まれる行を削除する
        data.dropna(inplace=True)

    # ★★★★★★★★★★★★★★★★ 修正箇所① ★★★★★★★★★★★★★★★★
    # 前処理後のデータフレームが空、または行が少なすぎる場合のチェックを強化
    if data.empty or len(data) < 1:
        st.warning(f"指定された期間に有効なデータが存在しません。期間や為替ペアを再設定してください。")
        st.stop()
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    # --- メインコンテンツの表示 ---
    st.subheader(f"{selected_pair_name} のチャート")

    # mplfinanceで描画
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

    # ★★★★★★★★★★★★★★★★ 修正箇所② ★★★★★★★★★★★★★★★★
    # figオブジェクトが正常に生成されたかを確認してから表示する
    if fig:
        st.pyplot(fig)
    else:
        st.error("チャートの描画に失敗しました。データが不十分である可能性があります。")
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    st.subheader("取得データ")
    st.dataframe(data.style.format("{:.4f}"))

except Exception as e:
    # ユーザーに見せるエラーメッセージをより具体的に
    st.error(f"処理中に予期せぬエラーが発生しました: {e}")
