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
st.info("サイドバーで2つの通貨を選択すると、市場で標準的な通貨ペアを自動で判別し、そのチャートと分析結果を表示します。")

# --- 設定データ ---
CURRENCY_HIERARCHY = ["EUR", "GBP", "AUD", "USD", "CAD", "CHF", "JPY"]
COT_ASSET_NAMES = {"EUR": "ユーロ", "USD": "米ドル", "JPY": "日本円", "GBP": "英ポンド", "AUD": "豪ドル", "CAD": "カナダドル", "CHF": "スイスフラン"}
TIMEZONE_MAP = {"日本時間 (JST)": "Asia/Tokyo", "米国東部時間 (EST/EDT)": "America/New_York", "協定世界時 (UTC)": "UTC"}
LOOKBACK_WEEKS = 26

# --- データ取得・処理関数 ---
@st.cache_data(ttl=3600)
def get_prepared_cot_data():
    df = cot.cot_all(cot_report_type='legacy_fut')
    columns_to_keep = ['Market and Exchange Names', 'As of Date in Form YYYY-MM-DD', 'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)', 'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)']
    df = df[columns_to_keep].copy(); df.rename(columns={'Market and Exchange Names': 'Name', 'As of Date in Form YYYY-MM-DD': 'Date', 'Noncommercial Positions-Long (All)': 'NonComm_Long', 'Noncommercial Positions-Short (All)': 'NonComm_Short', 'Commercial Positions-Long (All)': 'Comm_Long', 'Commercial Positions-Short (All)': 'Comm_Short'}, inplace=True); df['Date'] = pd.to_datetime(df['Date'])
    name_map = {"BRITISH POUND STERLING": "英ポンド", "JAPANESE YEN": "日本円", "CANADIAN DOLLAR": "カナダドル", "SWISS FRANC": "スイスフラン", "EURO FX": "ユーロ", "AUSTRALIAN DOLLAR": "豪ドル", "U.S. DOLLAR INDEX": "米ドル"}
    df['Name'] = df['Name'].apply(lambda x: name_map.get(x.split(' - ')[0], None)); df.dropna(subset=['Name'], inplace=True)
    df['NonComm_Net'] = df['NonComm_Long'] - df['NonComm_Short']; df['Comm_Net'] = df['Comm_Long'] - df['Comm_Short']
    return df.sort_values(by=['Name', 'Date'])

# --- 分析関数 ---
def get_cot_index(series, lookback):
    rolling_min = series.rolling(window=lookback).min(); rolling_max = series.rolling(window=lookback).max()
    return (series - rolling_min) / (rolling_max - rolling_min) * 100

def analyze_currency_pair(base_asset, quote_asset, all_cot_data):
    results = {}
    for asset_name in [base_asset, quote_asset]:
        asset_df = all_cot_data[all_cot_data['Name'] == asset_name]
        if len(asset_df) < LOOKBACK_WEEKS: return None
        latest = asset_df.iloc[-1]
        results[asset_name] = {"投機筋Net": latest['NonComm_Net'],"投機筋Idx": get_cot_index(asset_df['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1],"実需筋Net": latest['Comm_Net'],"実需筋Idx": get_cot_index(asset_df['Comm_Net'], LOOKBACK_WEEKS).iloc[-1]}
    base_score, quote_score = results[base_asset]["投機筋Idx"], results[quote_asset]["投機筋Idx"]
    pair_score = base_score - quote_score
    df = pd.DataFrame(results).T
    df["ペア総合スコア"] = [pair_score, np.nan]
    return df

# --- ヘルパー関数 ---
def get_pair_info(ccy1, ccy2):
    if CURRENCY_HIERARCHY.index(ccy1) < CURRENCY_HIERARCHY.index(ccy2):
        standard_base, standard_quote = ccy1, ccy2
    else:
        standard_base, standard_quote = ccy2, ccy1
    yfinance_ticker = f"{standard_base}{standard_quote}=X"
    if standard_base == 'USD': yfinance_ticker = f"{standard_quote}=X"
    return standard_base, standard_quote, yfinance_ticker

# --- メイン処理 ---
def main():
    st.sidebar.header("チャート設定")
    col1, col2 = st.sidebar.columns(2)
    with col1: ccy1 = st.selectbox("通貨1", CURRENCY_HIERARCHY, index=1)
    with col2: ccy2 = st.selectbox("通貨2", CURRENCY_HIERARCHY, index=6)

    selected_tz_name = st.sidebar.selectbox("表示タイムゾーン", list(TIMEZONE_MAP.keys()), index=0)
    today, start_date_default = datetime.now().date(), datetime.now().date() - timedelta(days=365)
    start_date = st.sidebar.date_input("開始日", start_date_default)
    end_date = st.sidebar.date_input("終了日", today)

    if ccy1 == ccy2: st.sidebar.error("異なる通貨を選択してください。"); st.stop()

    standard_base, standard_quote, yfinance_ticker = get_pair_info(ccy1, ccy2)
    standard_pair_name = f"{standard_base}/{standard_quote}"

    with st.sidebar.expander("デバッグ情報"):
        st.write(f"ユーザー選択: `{ccy1}` と `{ccy2}`"); st.write(f"市場標準ペア: `{standard_pair_name}`"); st.write(f"使用ティッカー: `{yfinance_ticker}`")

    try:
        intraday_data_utc = yf.download(tickers=yfinance_ticker, start=start_date, end=end_date + timedelta(days=1), interval="1h", progress=False)
        if intraday_data_utc.empty: st.warning(f"価格データを取得できませんでした。"); st.stop()
        if isinstance(intraday_data_utc.columns, pd.MultiIndex): intraday_data_utc.columns = intraday_data_utc.columns.droplevel(1)
        
        selected_tz = TIMEZONE_MAP[selected_tz_name]
        price_data = intraday_data_utc.tz_convert(selected_tz).resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        if price_data.empty: st.warning("データ処理の結果、表示できる価格データがありませんでした。"); st.stop()

        price_data['MA25'] = price_data['Close'].rolling(window=25).mean(); price_data['MA75'] = price_data['Close'].rolling(window=75).mean()
        
        st.header(f"{standard_pair_name} 価格チャート")
        fig = go.Figure(data=[go.Candlestick(x=price_data.index, open=price_data['Open'], high=price_data['High'], low=price_data['Low'], close=price_data['Close'], name='ローソク足')])
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA25'], mode='lines', name='25日移動平均線', line=dict(color='orange', width=1.5)))
        fig.add_trace(go.Scatter(x=price_data.index, y=price_data['MA75'], mode='lines', name='75日移動平均線', line=dict(color='purple', width=1.5)))

        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        # --- 修正箇所: 最新価格のラベル表示機能を復活 ---
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        annotations = []
        if not price_data.empty:
            latest_data = price_data.iloc[-1]
            latest_date = price_data.index[-1]
            
            # 終値のラベル
            annotations.append(dict(x=latest_date, y=latest_data.Close, text=f"{latest_data.Close:.3f}", showarrow=False, xanchor="left", xshift=5, font=dict(size=14, color="white"), bgcolor="rgba(0,0,139,0.8)", borderpad=4))
            # MA25のラベル
            if not pd.isna(latest_data.MA25):
                annotations.append(dict(x=latest_date, y=latest_data.MA25, text=f"{latest_data.MA25:.3f}", showarrow=False, xanchor="left", xshift=5, font=dict(size=12, color="white"), bgcolor="rgba(255,165,0,0.8)", borderpad=3))
            # MA75のラベル
            if not pd.isna(latest_data.MA75):
                annotations.append(dict(x=latest_date, y=latest_data.MA75, text=f"{latest_data.MA75:.3f}", showarrow=False, xanchor="left", xshift=5, font=dict(size=12, color="white"), bgcolor="rgba(128,0,128,0.8)", borderpad=3))
        
        fig.update_layout(
            height=500, xaxis_rangeslider_visible=False, margin=dict(t=30, b=30), 
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
            annotations=annotations # 作成したアノテーションを追加
        )
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        
        st.plotly_chart(fig, use_container_width=True)

        st.header(f"COTペア分析: {standard_pair_name}")
        base_asset_cot, quote_asset_cot = COT_ASSET_NAMES.get(standard_base), COT_ASSET_NAMES.get(standard_quote)
        
        if base_asset_cot and quote_asset_cot:
            with st.spinner('COTレポートデータを取得・分析中...'): analysis_df = analyze_currency_pair(base_asset_cot, quote_asset_cot, get_prepared_cot_data())
            if analysis_df is not None:
                st.info(f"**ペア総合スコア: {analysis_df.loc[base_asset_cot, 'ペア総合スコア']:.1f}** (正の値は {standard_base} が優勢、負の値は {standard_quote} が優勢を示唆)")
                def style_score(val): return f'color: {"green" if val > 0 else "red"}' if isinstance(val, (int, float)) else ''
                st.dataframe(analysis_df.style.format({"投機筋Net": "{:,.0f}", "実需筋Net": "{:,.0f}", "投機筋Idx": "{:.1f}", "実需筋Idx": "{:.1f}", "ペア総合スコア": "{:.1f}"}, na_rep="---").applymap(style_score, subset=['ペア総合スコア']), use_container_width=True)
            else: st.warning("分析に必要なCOTデータが不足しています。")
        else: st.info("この為替ペアに対応する直接的なCOTデータはありません。")

    except Exception as e:
        st.error(f"予期せぬエラーが発生しました。yfinanceがこの通貨ペアのデータを提供していない可能性があります。"); st.exception(e)

if __name__ == '__main__':
    main()
