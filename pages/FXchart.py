import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

def main():
    """
    時間足データを取得し、正確な日足にリサンプリングして描画する、データ精度向上版。
    yfinanceの日足データが不正確である問題を解決します。
    """
    st.set_page_config(layout="wide")
    st.title("💹 為替レート ローソク足チャート (高精度版)")
    st.info("内部的に時間足データを取得し、より正確な日足チャートを生成しています。")

    # --- サイドバーでの設定 ---
    st.sidebar.header("チャート設定")
    symbol_map = {
        "米ドル/円 (USDJPY)": "JPY=X",
        "ユーロ/円 (EURJPY)": "EURJPY=X",
        "ユーロ/米ドル (EURUSD)": "EURUSD=X",
        "ポンド/円 (GBPJPY)": "GBPJPY=X",
        "豪ドル/円 (AUDJPY)": "AUDJPY=X",
    }
    selected_name = st.sidebar.selectbox("為替ペアを選択", list(symbol_map.keys()))
    symbol = symbol_map[selected_name]

    # --- 開始日と終了日の設定 ---
    today = datetime.now().date()
    # yfinanceの時間足データは過去730日以内という制約があるため、デフォルトを調整
    start_date_default = today - timedelta(days=180) 
    
    start_date = st.sidebar.date_input("開始日", start_date_default)
    end_date = st.sidebar.date_input("終了日", today)

    if start_date >= end_date:
        st.sidebar.error("エラー: 終了日は開始日より後の日付にしてください。")
        st.stop()
    
    # yfinanceの時間足データ取得期間の制約チェック
    if (today - start_date).days > 729:
        st.sidebar.warning("警告: 時間足データは過去730日以内でないと取得できない場合があります。期間を短くしてください。")

    # --- データの取得と高精度な日足への変換 ---
    try:
        # ステップ1: 「時間足(1h)」のデータを取得する
        # intervalを'1h'にすることで、より細かいデータを取得
        intraday_data = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date + timedelta(days=1),
            interval="1h", # 時間足データを指定
            progress=False
        )

        if intraday_data.empty:
            st.warning("指定された期間のデータを取得できませんでした。")
            st.stop()
        
        # yfinanceが返すマルチレベルカラムをシングルレベルに平坦化
        if isinstance(intraday_data.columns, pd.MultiIndex):
            intraday_data.columns = intraday_data.columns.droplevel(1)

        # ステップ2: 時間足データを日足にリサンプリングする
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        data = intraday_data.resample('D').agg(ohlc_dict).dropna()
        
        # --- 移動平均線の計算 ---
        data['MA25'] = data['Close'].rolling(window=25).mean()
        data['MA75'] = data['Close'].rolling(window=75).mean()

        # --- チャートの描画 ---
        st.header(f"{selected_name} チャート")

        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='ローソク足'
        )])

        fig.add_trace(go.Scatter(x=data.index, y=data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=data.index, y=data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))

        fig.update_layout(
            height=800,
            title_text=f"{selected_name} 価格推移",
            xaxis_title="日付", yaxis_title="価格",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)
        st.subheader("表示データ（日足）")
        st.dataframe(data.style.format("{:.3f}"))

    except Exception as e:
        st.error("予期せぬエラーが発生しました。")
        st.exception(e)

if __name__ == '__main__':
    main()
