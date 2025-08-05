import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import cot_reports as cot # COTレポート用ライブラリを追加

# --- Streamlit ページ設定 ---
st.set_page_config(layout="wide")
st.title("💹 為替レート・COT分析チャート")
st.info("チャート下に、選択した通貨ペアに関連する最新のCOTレポート（投機筋のポジション動向）が表示されます。")


# --- 設定データ ---
# yfinance用
SYMBOL_MAP = {
    "米ドル/円 (USDJPY)": "JPY=X", "ユーロ/円 (EURJPY)": "EURJPY=X",
    "ユーロ/米ドル (EURUSD)": "EURUSD=X", "ポンド/円 (GBPJPY)": "GBPJPY=X",
    "豪ドル/円 (AUDJPY)": "AUDJPY=X",
}
# COTレポート用 (yfinanceの選択肢とCOTアセット名をマッピング)
COT_ASSET_MAP = {
    "米ドル/円 (USDJPY)": "日本円",
    "ユーロ/円 (EURJPY)": "ユーロ", # 円とユーロ両方あるが、主要な方を代表
    "ユーロ/米ドル (EURUSD)": "ユーロ",
    "ポンド/円 (GBPJPY)": "英ポンド",
    "豪ドル/円 (AUDJPY)": "豪ドル",
}
# タイムゾーン用
TIMEZONE_MAP = {
    "日本時間 (JST)": "Asia/Tokyo", "米国東部時間 (EST/EDT)": "America/New_York",
    "協定世界時 (UTC)": "UTC", "ロンドン時間 (GMT/BST)": "Europe/London",
}


# --- データ取得関数 (Streamlitのキャッシュ機能で高速化) ---
@st.cache_data(ttl=3600) # 1時間キャッシュ
def get_cot_data():
    """COTデータをまとめて取得し、前処理を行う"""
    df = cot.cot_all(cot_report_type='legacy_fut')
    # 必要な列のみを抽出し、列名を分かりやすく変更
    columns_to_keep = [
        'Market and Exchange Names', 'As of Date in Form YYYY-MM-DD',
        'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)',
        'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)',
        'Nonreportable Positions-Long (All)', 'Nonreportable Positions-Short (All)'
    ]
    df = df[columns_to_keep]
    df.rename(columns={
        'Market and Exchange Names': 'Name',
        'As of Date in Form YYYY-MM-DD': 'Date',
        'Noncommercial Positions-Long (All)': 'NonComm_Long',
        'Noncommercial Positions-Short (All)': 'NonComm_Short',
        'Commercial Positions-Long (All)': 'Comm_Long',
        'Commercial Positions-Short (All)': 'Comm_Short',
        'Nonreportable Positions-Long (All)': 'Retail_Long',
        'Nonreportable Positions-Short (All)': 'Retail_Short'
    }, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    # "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE" のような名前から主要な名前を抽出
    df['Name'] = df['Name'].apply(lambda x: x.split(' - ')[0].replace("BRITISH POUND", "英ポンド").replace("JAPANESE YEN", "日本円").replace("CANADIAN DOLLAR", "カナダドル").replace("SWISS FRANC", "スイスフラン").replace("EURO FX", "ユーロ").replace("AUSTRALIAN DOLLAR", "豪ドル").replace("U.S. DOLLAR INDEX", "米ドル"))
    return df


def main():
    # --- サイドバーでの設定 ---
    st.sidebar.header("チャート設定")
    selected_tz_name = st.sidebar.selectbox("表示タイムゾーン", list(TIMEZONE_MAP.keys()))
    selected_symbol_name = st.sidebar.selectbox("為替ペア", list(SYMBOL_MAP.keys()))
    
    today = datetime.now().date()
    start_date = st.sidebar.date_input("開始日", today - timedelta(days=180))
    end_date = st.sidebar.date_input("終了日", today)

    if start_date >= end_date:
        st.sidebar.error("エラー: 終了日は開始日より後の日付にしてください。")
        st.stop()

    # --- 価格データの取得と処理 ---
    try:
        symbol = SYMBOL_MAP[selected_symbol_name]
        selected_tz = TIMEZONE_MAP[selected_tz_name]
        
        intraday_data_utc = yf.download(tickers=symbol, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)

        if intraday_data_utc.empty:
            st.warning("指定された期間の価格データを取得できませんでした。")
            st.stop()
        
        if isinstance(intraday_data_utc.columns, pd.MultiIndex):
            intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)

        intraday_data_local = intraday_data_utc.tz_convert(selected_tz)
        ohlc_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        price_data = intraday_data_local.resample('D').agg(ohlc_dict).dropna()
        
        price_data['MA25'] = price_data['Close'].rolling(window=25).mean()
        price_data['MA75'] = price_data['Close'].rolling(window=75).mean()

        # --- チャート描画 ---
        st.header(f"{selected_symbol_name} チャート [{selected_tz_name}基準]")
        fig = go.Figure(data=[go.Candlestick(x=price_data.index, open=price_data['Open'], high=price_data['High'], low=price_data['Low'], close=price_data['Close'], name='ローソク足')])
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))
        fig.update_layout(height=700, title_text=f"{selected_symbol_name} 価格推移", xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)

        # --- COTレポートの表示 ---
        st.header(f"COTレポート分析: {COT_ASSET_MAP.get(selected_symbol_name, '---')}")
        cot_asset_name = COT_ASSET_MAP.get(selected_symbol_name)
        
        if cot_asset_name:
            all_cot_data = get_cot_data()
            asset_data = all_cot_data[all_cot_data['Name'] == cot_asset_name].sort_values(by='Date', ascending=False)
            
            if len(asset_data) >= 2:
                latest = asset_data.iloc[0]
                previous = asset_data.iloc[1]

                st.caption(f"最新データ日付: {latest['Date'].strftime('%Y-%m-%d')} (前週比)")
                
                # 表示用のデータフレームを作成
                def format_change(current, prev):
                    change = current - prev
                    return f"{current:,.0f} ({change:+,d})"

                table_data = {
                    "Long (枚)": [format_change(latest['Comm_Long'], previous['Comm_Long']),
                                format_change(latest['NonComm_Long'], previous['NonComm_Long']),
                                format_change(latest['Retail_Long'], previous['Retail_Long'])],
                    "Short (枚)": [format_change(latest['Comm_Short'], previous['Comm_Short']),
                                 format_change(latest['NonComm_Short'], previous['NonComm_Short']),
                                 format_change(latest['Retail_Short'], previous['Retail_Short'])],
                    "Net (枚)": [format_change(latest['Comm_Long'] - latest['Comm_Short'], previous['Comm_Long'] - previous['Comm_Short']),
                               format_change(latest['NonComm_Long'] - latest['NonComm_Short'], previous['NonComm_Long'] - previous['NonComm_Short']),
                               format_change(latest['Retail_Long'] - latest['Retail_Short'], previous['Retail_Long'] - previous['Retail_Short'])]
                }
                df_display = pd.DataFrame(table_data, index=["実需筋 (Commercials)", "大口投機筋 (Non-Commercials)", "小口投機筋 (Retail)"])
                st.dataframe(df_display, use_container_width=True)
            else:
                st.warning("この銘柄のCOTデータが不足しています。")
        else:
            st.info("この為替ペアに対応する直接的なCOTデータはありません。")

    except Exception as e:
        st.error("予期せぬエラーが発生しました。")
        st.exception(e)

if __name__ == '__main__':
    main()
