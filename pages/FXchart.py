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
st.info("チャート下に、最新のポジション分析、スコアの時系列推移、そして価格と同期した分析表が表示されます。")

# --- 設定データ ---
CURRENCY_HIERARCHY = ["EUR", "GBP", "AUD", "USD", "CAD", "CHF", "JPY"]
COT_ASSET_NAMES = {"EUR": "ユーロ", "USD": "米ドル", "JPY": "日本円", "GBP": "英ポンド", "AUD": "豪ドル", "CAD": "カナダドル", "CHF": "スイスフラン"}
TIMEZONE_MAP = {"日本時間 (JST)": "Asia/Tokyo", "米国東部時間 (EST/EDT)": "America/New_York", "協定世界時 (UTC)": "UTC"}
LOOKBACK_WEEKS = 26

# --- データ取得・処理関数 ---
@st.cache_data(ttl=3600)
def get_prepared_cot_data():
    df = cot.cot_all(cot_report_type='legacy_fut'); columns_to_keep = ['Market and Exchange Names', 'As of Date in Form YYYY-MM-DD', 'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)', 'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)']
    df = df[columns_to_keep].copy(); df.rename(columns={'Market and Exchange Names': 'Name', 'As of Date in Form YYYY-MM-DD': 'Date', 'Noncommercial Positions-Long (All)': 'NonComm_Long', 'Noncommercial Positions-Short (All)': 'NonComm_Short', 'Commercial Positions-Long (All)': 'Comm_Long', 'Commercial Positions-Short (All)': 'Comm_Short'}, inplace=True); df['Date'] = pd.to_datetime(df['Date'])
    name_map = {"BRITISH POUND STERLING": "英ポンド", "JAPANESE YEN": "日本円", "CANADIAN DOLLAR": "カナダドル", "SWISS FRANC": "スイスフラン", "EURO FX": "ユーロ", "AUSTRALIAN DOLLAR": "豪ドル", "U.S. DOLLAR INDEX": "米ドル"}
    df['Name'] = df['Name'].apply(lambda x: name_map.get(x.split(' - ')[0], None)); df.dropna(subset=['Name'], inplace=True)
    df['NonComm_Net'] = df['NonComm_Long'] - df['NonComm_Short']; df['Comm_Net'] = df['Comm_Long'] - df['Comm_Short']
    return df.sort_values(by=['Name', 'Date'])

@st.cache_data(ttl=3600)
def get_daily_price_data(ticker, start, end):
    return yf.download(ticker, start=start, end=end, progress=False)

# --- 分析関数 ---
def get_cot_index(series, lookback):
    rolling_min = series.rolling(window=lookback).min(); rolling_max = series.rolling(window=lookback).max()
    return (series - rolling_min) / (rolling_max - rolling_min) * 100

def analyze_currency_pair_snapshot(base_asset, quote_asset, all_cot_data):
    results = {}
    for asset_name in [base_asset, quote_asset]:
        asset_df = all_cot_data[all_cot_data['Name'] == asset_name];
        if len(asset_df) < LOOKBACK_WEEKS: return None
        latest = asset_df.iloc[-1]
        results[asset_name] = {"投機筋Net": latest['NonComm_Net'],"投機筋Idx": get_cot_index(asset_df['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1],"実需筋Net": latest['Comm_Net'],"実需筋Idx": get_cot_index(asset_df['Comm_Net'], LOOKBACK_WEEKS).iloc[-1]}
    base_score, quote_score = results[base_asset]["投機筋Idx"], results[quote_asset]["投機筋Idx"]
    pair_score = base_score - quote_score
    df = pd.DataFrame(results).T; df["ペア総合スコア"] = [pair_score, np.nan]
    return df

def analyze_score_history(base_asset, quote_asset, all_cot_data):
    base_df = all_cot_data[all_cot_data['Name'] == base_asset].drop_duplicates(subset='Date', keep='last').copy()
    quote_df = all_cot_data[all_cot_data['Name'] == quote_asset].drop_duplicates(subset='Date', keep='last').copy()
    if len(base_df) < LOOKBACK_WEEKS or len(quote_df) < LOOKBACK_WEEKS: return None
    base_df['NonComm_Idx'] = get_cot_index(base_df['NonComm_Net'], LOOKBACK_WEEKS)
    quote_df['NonComm_Idx'] = get_cot_index(quote_df['NonComm_Net'], LOOKBACK_WEEKS)
    base_series = base_df.set_index('Date')['NonComm_Idx']; quote_series = quote_df.set_index('Date')['NonComm_Idx']
    merged_df = pd.merge(base_series, quote_series, on='Date', how='inner', suffixes=('_base', '_quote'))
    merged_df['ペア総合スコア'] = merged_df['NonComm_Idx_base'] - merged_df['NonComm_Idx_quote']
    merged_df['週次変化'] = merged_df['ペア総合スコア'].diff()
    return merged_df[['ペア総合スコア', '週次変化']].dropna().sort_index(ascending=False)

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# --- 新しい分析関数: COTと価格の時系列を統合 ---
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
def create_cot_price_history_table(base_asset, quote_asset, ticker, start_date, end_date, all_cot_data):
    # 1. COTデータの準備
    base_cot = all_cot_data[all_cot_data['Name'] == base_asset].drop_duplicates(subset='Date', keep='last').set_index('Date')
    quote_cot = all_cot_data[all_cot_data['Name'] == quote_asset].drop_duplicates(subset='Date', keep='last').set_index('Date')
    if len(base_cot) < LOOKBACK_WEEKS or len(quote_cot) < LOOKBACK_WEEKS: return None

    # 2. 価格データの準備 (日足)
    price_history = get_daily_price_data(ticker, start_date, end_date + timedelta(days=1))
    if price_history.empty: return None

    # 3. COTデータと価格データを日付で結合
    combined = base_cot.join(price_history['Close'], how='left').rename(columns={'Close': '為替終値'})
    combined['投機筋Net(ベース)'] = combined['NonComm_Net']
    combined['投機筋Net(クオート)'] = quote_cot['NonComm_Net']
    
    # 4. ペア総合スコアの計算
    combined['投機筋Idx(ベース)'] = get_cot_index(combined['投機筋Net(ベース)'], LOOKBACK_WEEKS)
    combined['投機筋Idx(クオート)'] = get_cot_index(combined['投機筋Net(クオート)'], LOOKBACK_WEEKS)
    combined['ペア総合スコア'] = combined['投機筋Idx(ベース)'] - combined['投機筋Idx(クオート)']
    
    # 5. 表示する列を選択し、整形
    result_df = combined[['為替終値', 'ペア総合スコア', '投機筋Net(ベース)', '投機筋Net(クオート)']].dropna().sort_index(ascending=False)
    return result_df

# --- ヘルパー関数 ---
def get_pair_info(ccy1, ccy2):
    if CURRENCY_HIERARCHY.index(ccy1) < CURRENCY_HIERARCHY.index(ccy2): standard_base, standard_quote = ccy1, ccy2
    else: standard_base, standard_quote = ccy2, ccy1
    yfinance_ticker = f"{standard_base}{standard_quote}=X"
    if standard_base == 'USD': yfinance_ticker = f"{standard_quote}=X"
    return standard_base, standard_quote, yfinance_ticker

# --- メイン処理 ---
def main():
    st.sidebar.header("チャート設定")
    col1, col2 = st.sidebar.columns(2);
    with col1: ccy1 = st.selectbox("通貨1", CURRENCY_HIERARCHY, index=1)
    with col2: ccy2 = st.selectbox("通貨2", CURRENCY_HIERARCHY, index=6)
    selected_tz_name = st.sidebar.selectbox("表示タイムゾーン", list(TIMEZONE_MAP.keys()), index=0)
    today = datetime.now().date(); start_date = st.sidebar.date_input("開始日", today - timedelta(days=365)); end_date = st.sidebar.date_input("終了日", today)
    if ccy1 == ccy2: st.sidebar.error("異なる通貨を選択してください。"); st.stop()

    standard_base, standard_quote, yfinance_ticker = get_pair_info(ccy1, ccy2)
    standard_pair_name = f"{standard_base}/{standard_quote}"

    try:
        # 価格チャート表示 (変更なし)
        intraday_data_utc = yf.download(tickers=yfinance_ticker, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)
        if intraday_data_utc.empty: st.warning(f"価格データを取得できませんでした。"); st.stop()
        if isinstance(intraday_data_utc.columns, pd.MultiIndex): intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)
        price_data = intraday_data_utc.tz_convert(TIMEZONE_MAP[selected_tz_name]).resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        if price_data.empty: st.warning("データ処理の結果、表示できる価格データがありませんでした。"); st.stop()
        price_data['MA25'] = price_data['Close'].rolling(window=25).mean(); price_data['MA75'] = price_data['Close'].rolling(window=75).mean()
        st.header(f"{standard_pair_name} 価格チャート")
        fig = go.Figure(data=[go.Candlestick(x=price_data.index, open=price_data['Open'], high=price_data['High'], low=price_data['Low'], close=price_data['Close'], name='ローソク足')])
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=30, b=30), legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)

        # --- COT分析の表示 ---
        st.header(f"COTペア分析: {standard_pair_name}")
        base_asset_cot, quote_asset_cot = COT_ASSET_NAMES.get(standard_base), COT_ASSET_NAMES.get(standard_quote)
        if base_asset_cot and quote_asset_cot:
            with st.spinner('COTレポートデータを取得・分析中...'):
                all_cot_data = get_prepared_cot_data()
                snapshot_df = analyze_currency_pair_snapshot(base_asset_cot, quote_asset_cot, all_cot_data)
                history_df = analyze_score_history(base_asset_cot, quote_asset_cot, all_cot_data)
                price_history_df = create_cot_price_history_table(base_asset_cot, quote_asset_cot, yfinance_ticker, start_date - timedelta(days=365), end_date, all_cot_data) # 計算用に少し長くデータを取る

            st.subheader("最新ポジションのスナップショット")
            if snapshot_df is not None:
                st.info(f"**ペア総合スコア: {snapshot_df.loc[base_asset_cot, 'ペア総合スコア']:.1f}** (正の値は {standard_base} が優勢、負の値は {standard_quote} が優勢を示唆)")
                def style_score(val): return f'color: {"green" if val > 0 else "red"}' if isinstance(val, (int, float)) else ''
                st.dataframe(snapshot_df.style.format({"投機筋Net": "{:,.0f}", "実需筋Net": "{:,.0f}", "投機筋Idx": "{:.1f}", "実需筋Idx": "{:.1f}", "ペア総合スコア": "{:.1f}"}, na_rep="---").applymap(style_score, subset=['ペア総合スコア']), use_container_width=True)
            
            st.subheader("ペア総合スコアの時系列推移")
            if history_df is not None:
                def style_change(val):
                    if isinstance(val, (int, float)): color = 'green' if val > 0 else 'red' if val < 0 else 'gray'; return f'color: {color}'
                    return ''
                st.dataframe(history_df.style.format("{:.1f}", na_rep="---").applymap(style_change, subset=['週次変化']), height=300, use_container_width=True)
            
            # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
            # --- 新しいテーブル: COTと価格の同期 ---
            # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
            st.subheader("COTスコアと為替終値の時系列")
            if price_history_df is not None:
                st.dataframe(price_history_df.style.format({
                    "為替終値": "{:.3f}",
                    "ペア総合スコア": "{:.1f}",
                    "投機筋Net(ベース)": "{:,.0f}",
                    "投機筋Net(クオート)": "{:,.0f}",
                }), height=300, use_container_width=True)
            else:
                st.warning("価格と同期した時系列分析に必要なデータが不足しています。")

        else: st.info("この為替ペアに対応する直接的なCOTデータはありません。")

    except Exception as e:
        st.error(f"予期せぬエラーが発生しました。"); st.exception(e)

if __name__ == '__main__':
    main()
