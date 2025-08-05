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
    # 1. auto_adjust=False を指定して、'Open', 'High', 'Low', 'Close' 列を確実に取得
    data = yf.download(
        ticker,
        start=start_date,
        end=end_date + timedelta(days=1),
        auto_adjust=False
    )

    if not data.empty:
        # 2. 対象となるカラムのデータ型を強制的に数値に変換
        cols_to_numeric = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in cols_to_numeric:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        # 3. NaNが含まれる行を削除する
        data.dropna(inplace=True)

    if data.empty:
        st.warning(f"指定された期間に有効なデータが存在しません。期間や為替ペアを再設定してください。")
        st.stop()
    
    # ★★★★★★★★★★★★★★★★ 修正箇所② (デバッグ情報) ★★★★★★★★★★★★★★★★
    # グラフ描画前のデータ件数を表示
    st.info(f"クリーニング後の有効なデータ件数: {len(data)}件")
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

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
        # ★★★★★★★★★★★★★★★★ 修正箇所① (Mavを無効化) ★★★★★★★★★★★★★★
        # mav=(5, 25), # 原因切り分けのため、移動平均線の描画を一時的にコメントアウト
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
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
