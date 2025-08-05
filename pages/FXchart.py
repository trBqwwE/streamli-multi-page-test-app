import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

def main():
    """
    最新の価格データをチャート右端にアノテーションとして表示する、最終完成版。
    """
    st.set_page_config(layout="wide")
    st.title("💹 為替レート ローソク足チャート (最新価格表示付き)")
    st.info("チャート右端に、各指標の最新の数値がラベルで表示されます。")

    # --- サイドバーでの設定 ---
    st.sidebar.header("チャート設定")
    
    # タイムゾーンの選択
    timezone_map = {
        "日本時間 (JST)": "Asia/Tokyo",
        "米国東部時間 (EST/EDT)": "America/New_York",
        "協定世界時 (UTC)": "UTC",
        "ロンドン時間 (GMT/BST)": "Europe/London",
        "シンガポール時間 (SGT)": "Asia/Singapore",
    }
    selected_tz_name = st.sidebar.selectbox("表示タイムゾーンを選択", options=list(timezone_map.keys()))
    selected_tz = timezone_map[selected_tz_name]

    # 為替ペアの選択
    symbol_map = {
        "米ドル/円 (USDJPY)": "JPY=X", "ユーロ/円 (EURJPY)": "EURJPY=X",
        "ユーロ/米ドル (EURUSD)": "EURUSD=X", "ポンド/円 (GBPJPY)": "GBPJPY=X",
        "豪ドル/円 (AUDJPY)": "AUDJPY=X",
    }
    selected_symbol_name = st.sidebar.selectbox("為替ペアを選択", list(symbol_map.keys()))
    symbol = symbol_map[selected_symbol_name]

    # 開始日と終了日の設定
    today = datetime.now().date()
    start_date_default = today - timedelta(days=180) 
    start_date = st.sidebar.date_input("開始日", start_date_default)
    end_date = st.sidebar.date_input("終了日", today)

    if start_date >= end_date:
        st.sidebar.error("エラー: 終了日は開始日より後の日付にしてください。")
        st.stop()
    
    if (today - start_date).days > 729:
        st.sidebar.warning("警告: 時間足データは過去730日以内でないと取得できない場合があります。")

    # --- データの取得と高精度な日足への変換 ---
    try:
        # ステップ1: 「時間足(1h)」のデータを取得
        intraday_data_utc = yf.download(tickers=symbol, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)

        if intraday_data_utc.empty:
            st.warning("指定された期間のデータを取得できませんでした。")
            st.stop()
        
        if isinstance(intraday_data_utc.columns, pd.MultiIndex):
            intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)

        # ステップ2: ユーザー指定のタイムゾーンに変換し、日足にリサンプリング
        intraday_data_local = intraday_data_utc.tz_convert(selected_tz)
        ohlc_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        data = intraday_data_local.resample('D').agg(ohlc_dict).dropna()
        
        data['MA25'] = data['Close'].rolling(window=25).mean()
        data['MA75'] = data['Close'].rolling(window=75).mean()

        # --- チャートの描画 ---
        st.header(f"{selected_symbol_name} チャート [{selected_tz_name}基準]")

        fig = go.Figure()

        # ローソク足と移動平均線を追加
        fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name='ローソク足'))
        fig.add_trace(go.Scatter(x=data.index, y=data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=data.index, y=data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))

        # ★★★★★★★★★★★★★★★★★★★ 修正箇所 ★★★★★★★★★★★★★★★★★★★
        # --- 最新の価格をチャート右にアノテーションとして表示 ---
        latest_data = data.iloc[-1]
        latest_date = data.index[-1]
        
        annotations = []
        
        # 終値のラベル
        annotations.append(dict(
            x=latest_date, y=latest_data.Close, xref="x", yref="y",
            text=f"{latest_data.Close:.3f}", showarrow=False, xanchor="left", xshift=5,
            font=dict(size=14, color="white"), bgcolor="rgba(0,0,139,0.8)", borderpad=4
        ))
        
        # MA25のラベル (データが存在する場合のみ)
        if not pd.isna(latest_data.MA25):
            annotations.append(dict(
                x=latest_date, y=latest_data.MA25, xref="x", yref="y",
                text=f"{latest_data.MA25:.3f}", showarrow=False, xanchor="left", xshift=5,
                font=dict(size=12, color="white"), bgcolor="rgba(255,165,0,0.8)", borderpad=3
            ))
            
        # MA75のラベル (データが存在する場合のみ)
        if not pd.isna(latest_data.MA75):
            annotations.append(dict(
                x=latest_date, y=latest_data.MA75, xref="x", yref="y",
                text=f"{latest_data.MA75:.3f}", showarrow=False, xanchor="left", xshift=5,
                font=dict(size=12, color="white"), bgcolor="rgba(128,0,128,0.8)", borderpad=3
            ))

        # グラフのレイアウトを更新
        fig.update_layout(
            height=800,
            title_text=f"{selected_symbol_name} 価格推移",
            xaxis_title=f"日付 ({selected_tz_name})", yaxis_title="価格",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            annotations=annotations # 作成したアノテーションを追加
        )
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        
        st.plotly_chart(fig, use_container_width=True)
        st.subheader(f"表示データ ({selected_tz_name}基準の日足)")
        st.dataframe(data.style.format("{:.3f}"))

    except Exception as e:
        st.error("予期せぬエラーが発生しました。")
        st.exception(e)

if __name__ == '__main__':
    main()
