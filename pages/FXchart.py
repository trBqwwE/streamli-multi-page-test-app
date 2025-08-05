import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- Streamlit アプリの基本設定 ---
st.set_page_config(
    page_title="【デバッグ用】データ調査アプリ",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍【デバッグ用】データ調査アプリ")
st.write("このアプリはグラフを描画せず、エラーの原因を特定するためにデータの内部を調査します。")
st.info("お手数ですが、この画面に表示された内容をコピーし、ご返信いただけますでしょうか。")

# --- サイドバー ---
st.sidebar.header("設定")
currency_pairs = {
    "米ドル/円 (USD/JPY)": "JPY=X",
    "ユーロ/円 (EUR/JPY)": "EURJPY=X",
    "豪ドル/円 (AUD/JPY)": "AUDJPY=X",
}
selected_pair_name = st.sidebar.selectbox("為替ペアを選択してください", list(currency_pairs.keys()))
ticker = currency_pairs[selected_pair_name]

end_date = datetime.now().date()
start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=30)) # 期間を短くして調査
end_date = st.sidebar.date_input("終了日", end_date)

if start_date > end_date:
    st.sidebar.error("エラー: 終了日は開始日より後の日付を選択してください。")
    st.stop()

# --- データ取得と調査 ---
try:
    st.header("ステップ1: yfinanceからの生データ調査")
    
    # auto_adjust=False を指定してデータを取得
    raw_data = yf.download(
        ticker,
        start=start_date,
        end=end_date + timedelta(days=1),
        auto_adjust=False,
        progress=False
    )

    if raw_data is None:
        st.error("yf.downloadの結果が `None` でした。データが取得できていません。")
        st.stop()
    
    st.write("yfinanceから取得した直後のデータフレーム:")
    st.dataframe(raw_data)
    
    st.write("yfinanceから取得した直後のデータフレーム情報 (`.info()`):")
    st.text(raw_data.info())


    st.header("ステップ2: データクリーニング後の調査")

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = raw_data[required_columns].copy()
    
    for col in required_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    data.dropna(inplace=True)

    st.write("クリーニング後のデータフレーム:")
    st.dataframe(data)

    st.write("クリーニング後のデータフレーム情報 (`.info()`):")
    st.text(data.info())
    
    st.header("最終確認")
    st.success("ここまでの処理でエラーが発生しなければ、データ自体は正常に整形されています。")
    st.write("もしこのメッセージが表示されているにも関わらず、元のコードでエラーが出る場合、Streamlit Cloudの環境自体に、こちらでは解決できない問題が存在する可能性が極めて高いです。")


except Exception as e:
    st.error(f"処理の途中でエラーが発生しました。")
    st.exception(e) # エラーの詳細情報を表示
