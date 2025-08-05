import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

def main():
    """
    yfinanceのマルチレベルカラム問題を解決し、安定してチャートを描画する最終版コード。
    """
    st.set_page_config(layout="wide")
    st.title("💹 為替レート ローソク足チャート (最終解決版)")

    # --- サイドバーでの設定 ---
    st.sidebar.header("チャート設定")
    symbol_map = {
        "米ドル/円 (USDJPY)": "JPY=X",
        "ユーロ/円 (EURJPY)": "EURJPY=X",
        "ユーロ/米ドル (EURUSD)": "EURUSD=X",
    }
    selected_name = st.sidebar.selectbox("為替ペアを選択", list(symbol_map.keys()))
    symbol = symbol_map[selected_name]

    end_date = datetime.now().date()
    start_date = st.sidebar.date_input("開始日", end_date - timedelta(days=365))

    # --- データの取得と問題の解決 ---
    try:
        # ステップ1: yfinanceからデータをダウンロード
        data = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date,
            progress=False
        )

        if data.empty:
            st.warning("指定された期間のデータを取得できませんでした。")
            st.stop()
            
        # ★★★★★★★★★★★★★★★★★★★ 根本原因の解決 ★★★★★★★★★★★★★★★★★★★
        # yfinanceが返すマルチレベルカラム（二階建てカラム）を、
        # シンプルなシングルレベル（一階建て）に平坦化する。
        data.columns = data.columns.droplevel(1)
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

        # --- チャートの描画 ---
        st.header(f"{selected_name} チャート")

        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name=selected_name
        )])

        fig.update_layout(
            height=800,
            title_text=f"{selected_name} 価格推移",
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(fig, use_container_width=True)

        # データのテーブル表示
        st.subheader("表示データ")
        st.dataframe(data.style.format("{:.3f}"))

    except Exception as e:
        st.error("予期せぬエラーが発生しました。")
        st.exception(e)

if __name__ == '__main__':
    main()
