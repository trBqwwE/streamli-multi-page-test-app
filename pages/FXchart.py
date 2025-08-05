import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import cot_reports as cot
import numpy as np

# --- Streamlit ページ設定 ---
st.set_page_config(layout="wide")
st.title("💹 為替レート・COTペア分析チャート")
st.info("チャート下に、選択した通貨ペアを構成する2通貨の力関係を分析したCOTレポートが表示されます。")

# --- 設定データ ---
SYMBOL_MAP = {
    "ユーロ/米ドル (EURUSD)": "EURUSD=X", "米ドル/円 (USDJPY)": "JPY=X",
    "ポンド/米ドル (GBPUSD)": "GBPUSD=X", "豪ドル/米ドル (AUDUSD)": "AUDUSD=X",
    "米ドル/カナダドル (USDCAD)": "CAD=X", "米ドル/スイスフラン (USDCHF)": "CHF=X",
}
COT_ASSET_MAP = {
    "ユーロ/米ドル (EURUSD)": ("ユーロ", "米ドル"), "米ドル/円 (USDJPY)": ("米ドル", "日本円"),
    "ポンド/米ドル (GBPUSD)": ("英ポンド", "米ドル"), "豪ドル/米ドル (AUDUSD)": ("豪ドル", "米ドル"),
    "米ドル/カナダドル (USDCAD)": ("米ドル", "カナダドル"), "米ドル/スイスフラン (USDCHF)": ("米ドル", "スイスフラン"),
}
TIMEZONE_MAP = {"日本時間 (JST)": "Asia/Tokyo", "米国東部時間 (EST/EDT)": "America/New_York", "協定世界時 (UTC)": "UTC"}
LOOKBACK_WEEKS = 26

# --- データ取得・処理関数 ---
@st.cache_data(ttl=3600)
def get_prepared_cot_data():
    df = cot.cot_all(cot_report_type='legacy_fut')
    columns_to_keep = ['Market and Exchange Names', 'As of Date in Form YYYY-MM-DD', 'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)', 'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)']
    df = df[columns_to_keep].copy()
    df.rename(columns={'Market and Exchange Names': 'Name', 'As of Date in Form YYYY-MM-DD': 'Date', 'Noncommercial Positions-Long (All)': 'NonComm_Long', 'Noncommercial Positions-Short (All)': 'NonComm_Short', 'Commercial Positions-Long (All)': 'Comm_Long', 'Commercial Positions-Short (All)': 'Comm_Short'}, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    name_map = {"BRITISH POUND STERLING": "英ポンド", "JAPANESE YEN": "日本円", "CANADIAN DOLLAR": "カナダドル", "SWISS FRANC": "スイスフラン", "EURO FX": "ユーロ", "AUSTRALIAN DOLLAR": "豪ドル", "U.S. DOLLAR INDEX": "米ドル"}
    df['Name'] = df['Name'].apply(lambda x: name_map.get(x.split(' - ')[0], None))
    df.dropna(subset=['Name'], inplace=True)
    df['NonComm_Net'] = df['NonComm_Long'] - df['NonComm_Short']
    df['Comm_Net'] = df['Comm_Long'] - df['Comm_Short']
    df = df.sort_values(by=['Name', 'Date'])
    return df

# --- 分析関数 ---
def get_cot_index(series, lookback):
    rolling_min = series.rolling(window=lookback).min()
    rolling_max = series.rolling(window=lookback).max()
    return (series - rolling_min) / (rolling_max - rolling_min) * 100

def analyze_currency_pair(base_asset, quote_asset, all_cot_data):
    results = {}
    for asset_name, position_type in [(base_asset, "ベース通貨"), (quote_asset, "クオート通貨")]:
        asset_df = all_cot_data[all_cot_data['Name'] == asset_name]
        if len(asset_df) < LOOKBACK_WEEKS: return None
        latest = asset_df.iloc[-1]
        results[position_type] = {"通貨名": asset_name, "投機筋ネットポジション": latest['NonComm_Net'], "投機筋COT指数": get_cot_index(asset_df['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1], "実需筋ネットポジション": latest['Comm_Net'], "実需筋COT指数": get_cot_index(asset_df['Comm_Net'], LOOKBACK_WEEKS).iloc[-1]}
    base_score, quote_score = results["ベース通貨"]["投機筋COT指数"], results["クオート通貨"]["投機筋COT指数"]
    pair_score = quote_score - base_score if base_asset == "米ドル" else base_score - quote_score
    df = pd.DataFrame(results).T
    df["ペア総合スコア"] = [pair_score, np.nan]
    return df

# --- メイン処理 ---
def main():
    st.sidebar.header("チャート設定")
    selected_symbol_name = st.sidebar.selectbox("為替ペア", list(SYMBOL_MAP.keys()))
    selected_tz_name = st.sidebar.selectbox("表示タイムゾーン", list(TIMEZONE_MAP.keys()), index=0)
    today = datetime.now().date()
    start_date = st.sidebar.date_input("開始日", today - timedelta(days=365))
    end_date = st.sidebar.date_input("終了日", today)

    if start_date >= end_date:
        st.sidebar.error("エラー: 終了日は開始日より後の日付にしてください。")
        st.stop()

    try:
        # --- 価格データの取得と高精度な日足への変換 ---
        symbol, selected_tz = SYMBOL_MAP[selected_symbol_name], TIMEZONE_MAP[selected_tz_name]
        intraday_data_utc = yf.download(tickers=symbol, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)

        if intraday_data_utc.empty:
            st.warning("指定された期間の価格データを取得できませんでした。"); st.stop()
        if isinstance(intraday_data_utc.columns, pd.MultiIndex):
            intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)
        
        intraday_data_local = intraday_data_utc.tz_convert(selected_tz)
        ohlc_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        price_data = intraday_data_local.resample('D').agg(ohlc_dict).dropna()

        if price_data.empty:
            st.warning("データ処理の結果、表示できる価格データがありませんでした。"); st.stop()

        # ★★★★★★★★★★★ 修正箇所① ★★★★★★★★★★★
        # --- 移動平均線の計算 ---
        price_data['MA25'] = price_data['Close'].rolling(window=25).mean()
        price_data['MA75'] = price_data['Close'].rolling(window=75).mean()
        
        # --- 価格チャートの表示 ---
        st.header(f"{selected_symbol_name} 価格チャート")
        fig = go.Figure(data=[go.Candlestick(x=price_data.index, open=price_data['Open'], high=price_data['High'], low=price_data['Low'], close=price_data['Close'], name='ローソク足')])

        # ★★★★★★★★★★★ 修正箇所② ★★★★★★★★★★★
        # --- 移動平均線をチャートに追加 ---
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))
        
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=30, b=30), legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)

        # --- COT分析の表示 ---
        st.header(f"COTペア分析: {selected_symbol_name}")
        base_asset, quote_asset = COT_ASSET_MAP.get(selected_symbol_name, (None, None))
        
        if base_asset and quote_asset:
            with st.spinner('COTレポートデータを取得・分析中...'):
                all_cot_data = get_prepared_cot_data()
                analysis_df = analyze_currency_pair(base_asset, quote_asset, all_cot_data)
            
            if analysis_df is not None:
                st.info(f"**ペア総合スコア: {analysis_df.loc['ベース通貨', 'ペア総合スコア']:.1f}** (正の値はベース通貨が優勢、負の値はクオート通貨が優勢を示唆)")
                def style_score(val):
                    return f'color: {"green" if val > 0 else "red"}' if isinstance(val, (int, float)) else ''
                st.dataframe(analysis_df.style.format({"投機筋ネットポジション": "{:,.0f}", "実需筋ネットポジション": "{:,.0f}", "投機筋COT指数": "{:.1f}", "実需筋COT指数": "{:.1f}", "ペア総合スコア": "{:.1f}"}, na_rep="---").applymap(style_score, subset=['ペア総合スコア']), use_container_width=True)
            else: st.warning("分析に必要なCOTデータが不足しています。")
        else: st.info("この為替ペアに対応する直接的なCOTデータはありません。")

    except Exception as e:
        st.error("予期せぬエラーが発生しました。"); st.exception(e)

if __name__ == '__main__':
    main()
