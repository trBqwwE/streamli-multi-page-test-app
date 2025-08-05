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
st.info("サイドバーで2つの通貨を選択すると、通貨の順番を自動で判別し、正しい通貨ペアとして分析を実行します。")

# --- 設定データ ---
# 市場での慣例的な通貨の序列 (この順番がベース通貨の優先順位となる)
CURRENCY_HIERARCHY = ["EUR", "GBP", "AUD", "USD", "CAD", "CHF", "JPY"]
COT_ASSET_NAMES = {"EUR": "ユーロ", "USD": "米ドル", "JPY": "日本円", "GBP": "英ポンド", "AUD": "豪ドル", "CAD": "カナダドル", "CHF": "スイスフラン"}
TIMEZONE_MAP = {"日本時間 (JST)": "Asia/Tokyo", "米国東部時間 (EST/EDT)": "America/New_York", "協定世界時 (UTC)": "UTC"}
LOOKBACK_WEEKS = 26

# --- データ取得・処理関数 (変更なし) ---
@st.cache_data(ttl=3600)
def get_prepared_cot_data():
    df = cot.cot_all(cot_report_type='legacy_fut')
    columns_to_keep = ['Market and Exchange Names', 'As of Date in Form YYYY-MM-DD', 'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)', 'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)']
    df = df[columns_to_keep].copy(); df.rename(columns={'Market and Exchange Names': 'Name', 'As of Date in Form YYYY-MM-DD': 'Date', 'Noncommercial Positions-Long (All)': 'NonComm_Long', 'Noncommercial Positions-Short (All)': 'NonComm_Short', 'Commercial Positions-Long (All)': 'Comm_Long', 'Commercial Positions-Short (All)': 'Comm_Short'}, inplace=True); df['Date'] = pd.to_datetime(df['Date'])
    name_map = {"BRITISH POUND STERLING": "英ポンド", "JAPANESE YEN": "日本円", "CANADIAN DOLLAR": "カナダドル", "SWISS FRANC": "スイスフラン", "EURO FX": "ユーロ", "AUSTRALIAN DOLLAR": "豪ドル", "U.S. DOLLAR INDEX": "米ドル"}
    df['Name'] = df['Name'].apply(lambda x: name_map.get(x.split(' - ')[0], None)); df.dropna(subset=['Name'], inplace=True)
    df['NonComm_Net'] = df['NonComm_Long'] - df['NonComm_Short']; df['Comm_Net'] = df['Comm_Long'] - df['Comm_Short']
    return df.sort_values(by=['Name', 'Date'])

# --- 分析関数 (変更なし) ---
def get_cot_index(series, lookback):
    rolling_min = series.rolling(window=lookback).min(); rolling_max = series.rolling(window=lookback).max()
    return (series - rolling_min) / (rolling_max - rolling_min) * 100

def analyze_currency_pair(base_asset, quote_asset, all_cot_data):
    results = {}
    for asset_name, position_type in [(base_asset, "ベース通貨"), (quote_asset, "クオート通貨")]:
        asset_df = all_cot_data[all_cot_data['Name'] == asset_name]
        if len(asset_df) < LOOKBACK_WEEKS: return None
        latest = asset_df.iloc[-1]
        results[position_type] = {"通貨名": asset_name, "投機筋ネットポジション": latest['NonComm_Net'], "投機筋COT指数": get_cot_index(asset_df['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1], "実需筋ネットポジション": latest['Comm_Net'], "実需筋COT指数": get_cot_index(asset_df['Comm_Net'], LOOKBACK_WEEKS).iloc[-1]}
    base_score, quote_score = results["ベース通貨"]["投機筋COT指数"], results["クオート通貨"]["投機筋COT指数"]
    pair_score = base_score - quote_score
    df = pd.DataFrame(results).T; df["ペア総合スコア"] = [pair_score, np.nan]
    return df

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# --- 修正・改善されたヘルパー関数 ---
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
def get_pair_info(ccy1, ccy2):
    """2つの通貨から、市場の標準ペア、反転フラグ、yfinanceティッカーを返す"""
    # 通貨の序列に基づき、標準的なベース通貨とクオート通貨を決定
    if CURRENCY_HIERARCHY.index(ccy1) < CURRENCY_HIERARCHY.index(ccy2):
        standard_base, standard_quote, is_inverted = ccy1, ccy2, False
    else:
        standard_base, standard_quote, is_inverted = ccy2, ccy1, True

    # yfinance用のティッカーを生成
    # USDがベース通貨の場合のみ、ティッカー形式が特殊 (例: JPY=X)
    if standard_base == 'USD':
        yfinance_ticker = f"{standard_quote}=X"
    else:
        yfinance_ticker = f"{standard_base}{standard_quote}=X"
        
    return standard_base, standard_quote, is_inverted, yfinance_ticker

# --- メイン処理 ---
def main():
    st.sidebar.header("チャート設定")
    col1, col2 = st.sidebar.columns(2)
    with col1: ccy1 = st.selectbox("通貨1", CURRENCY_HIERARCHY, index=1) # USD
    with col2: ccy2 = st.selectbox("通貨2", CURRENCY_HIERARCHY, index=6) # JPY

    selected_tz_name = st.sidebar.selectbox("表示タイムゾーン", list(TIMEZONE_MAP.keys()), index=0)
    today = datetime.now().date()
    start_date = st.sidebar.date_input("開始日", today - timedelta(days=365))
    end_date = st.sidebar.date_input("終了日", today)

    if ccy1 == ccy2: st.sidebar.error("異なる通貨を選択してください。"); st.stop()

    # --- 通貨ペアの正規化と動的な名称生成 ---
    standard_base, standard_quote, is_inverted, yfinance_ticker = get_pair_info(ccy1, ccy2)
    user_selected_pair_name = f"{ccy1}/{ccy2}"

    # --- デバッグ情報の表示 ---
    with st.sidebar.expander("デバッグ情報"):
        st.write(f"ユーザー選択: `{user_selected_pair_name}`")
        st.write(f"市場標準ペア: `{standard_base}/{standard_quote}`")
        st.write(f"価格を反転表示: `{'はい' if is_inverted else 'いいえ'}`")
        st.write(f"使用ティッカー: `{yfinance_ticker}`")

    try:
        # --- 価格データの取得 ---
        intraday_data_utc = yf.download(tickers=yfinance_ticker, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)
        if intraday_data_utc.empty: st.warning(f"価格データを取得できませんでした。"); st.stop()
        if isinstance(intraday_data_utc.columns, pd.MultiIndex): intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)
        
        # --- 価格データの反転処理 ---
        if is_inverted:
            inverted_data = pd.DataFrame()
            inverted_data['Open'] = 1 / intraday_data_utc['Open']
            inverted_data['High'] = 1 / intraday_data_utc['Low']; inverted_data['Low'] = 1 / intraday_data_utc['High']
            inverted_data['Close'] = 1 / intraday_data_utc['Close']; inverted_data['Volume'] = intraday_data_utc['Volume']
            intraday_data_utc = inverted_data

        # --- 日足への変換とチャート描画 ---
        selected_tz = TIMEZONE_MAP[selected_tz_name]
        price_data = intraday_data_utc.tz_convert(selected_tz).resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        if price_data.empty: st.warning("データ処理の結果、表示できる価格データがありませんでした。"); st.stop()

        price_data['MA25'] = price_data['Close'].rolling(window=25).mean(); price_data['MA75'] = price_data['Close'].rolling(window=75).mean()
        
        st.header(f"{user_selected_pair_name} 価格チャート")
        fig = go.Figure(data=[go.Candlestick(x=price_data.index, open=price_data['Open'], high=price_data['High'], low=price_data['Low'], close=price_data['Close'], name='ローソク足')])
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=30, b=30), legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)

        # --- COT分析の表示 ---
        st.header(f"COTペア分析: {user_selected_pair_name}")
        base_asset_cot, quote_asset_cot = COT_ASSET_NAMES.get(ccy1), COT_ASSET_NAMES.get(ccy2)
        if base_asset_cot and quote_asset_cot:
            with st.spinner('COTレポートデータを取得・分析中...'): analysis_df = analyze_currency_pair(base_asset_cot, quote_asset_cot, get_prepared_cot_data())
            if analysis_df is not None:
                st.info(f"**ペア総合スコア: {analysis_df.loc['ベース通貨', 'ペア総合スコア']:.1f}** (正の値は {ccy1} が優勢、負の値は {ccy2} が優勢を示唆)")
                def style_score(val): return f'color: {"green" if val > 0 else "red"}' if isinstance(val, (int, float)) else ''
                st.dataframe(analysis_df.style.format({"投機筋ネットポジション": "{:,.0f}", "実需筋ネットポジション": "{:,.0f}", "投機筋COT指数": "{:.1f}", "実需筋COT指数": "{:.1f}", "ペア総合スコア": "{:.1f}"}, na_rep="---").applymap(style_score, subset=['ペア総合スコア']), use_container_width=True)
            else: st.warning("分析に必要なCOTデータが不足しています。")
        else: st.info("この為替ペアに対応する直接的なCOTデータはありません。")

    except Exception as e:
        st.error(f"予期せぬエラーが発生しました。yfinanceがこの通貨ペアのデータを提供していない可能性があります。"); st.exception(e)

if __name__ == '__main__':
    main()
