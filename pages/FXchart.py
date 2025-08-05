import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

def main():
    """
    yfinanceから為替データを取得し、ローソク足と移動平均線を描画する最終版アプリ。
    yfinance特有のマルチレベルカラム問題を解決済み。
    """
    st.set_page_config(layout="wide")
    st.title("💹 為替レート ローソク足チャート")

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
    start_date_default = today - timedelta(days=365)
    
    start_date = st.sidebar.date_input("開始日", start_date_default)
    end_date = st.sidebar.date_input("終了日", today)

    if start_date >= end_date:
        st.sidebar.error("エラー: 終了日は開始日より後の日付にしてください。")
        st.stop()

    # --- データの取得と問題の解決 ---
    try:
        # yfinanceからデータをダウンロード (終了日もデータに含めるため+1日する)
        data = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date + timedelta(days=1),
            progress=False
        )

        if data.empty:
            st.warning("指定された期間のデータを取得できませんでした。")
            st.stop()
            
        # yfinanceが返すマルチレベルカラム（二階建て）をシングルレベルに平坦化する
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        # --- 移動平均線の計算 ---
        data['MA25'] = data['Close'].rolling(window=25).mean()
        data['MA75'] = data['Close'].rolling(window=75).mean()

        # --- チャートの描画 ---
        st.header(f"{selected_name} チャート")

        # ローソク足のメイン部分を作成
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='ローソク足'
        )])

        # 移動平均線をチャートに追加
        fig.add_trace(go.Scatter(
            x=data.index, 
            y=data['MA25'], 
            mode='lines', 
            name='25日移動平均線',
            line=dict(color='orange', width=1.5)
        ))
        fig.add_trace(go.Scatter(
            x=data.index, 
            y=data['MA75'], 
            mode='lines', 
            name='75日移動平均線',
            line=dict(color='purple', width=1.5)
        ))

        # グラフのレイアウトを更新
        fig.update_layout(
            height=800,
            title_text=f"{selected_name} 価格推移",
            xaxis_title="日付",
            yaxis_title="価格",
            xaxis_rangeslider_visible=False, # 下部のレンジスライダーは非表示
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # 凡例をグラフ上部に表示
        )

        st.plotly_chart(fig, use_container_width=True)

        # データのテーブル表示
        st.subheader("表示データ（移動平均線含む）")
        st.dataframe(data.style.format("{:.3f}"))

    except Exception as e:
        st.error("予期せぬエラーが発生しました。")
        st.exception(e)

if __name__ == '__main__':
    main()
