import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import time
import warnings

# --- 1. 定数と共通設定 ---
warnings.filterwarnings('ignore', category=UserWarning)
try:
    plt.rcParams['font.family'] = 'IPAGothic'
except RuntimeError:
    st.warning("日本語フォント（IPAGothic）が見つかりません。正しく表示されない可能性があります。")
plt.rcParams['axes.unicode_minus'] = False

# --- 日本市場の定義 ---
JP_BENCHMARK_TICKER = '1306.T' # TOPIX連動ETF
JP_SECTOR_TICKERS = [
    '1617.T', '1618.T', '1619.T', '1620.T', '1621.T', '1622.T', '1623.T', '1624.T',
    '1625.T', '1626.T', '1627.T', '1628.T', '1629.T', '1630.T', '1631.T', '1632.T', '1633.T'
]
JP_THEMATIC_TICKERS = ['1308.T', '1311.T', '1312.T', '2644.T', '1473.T', '1474.T']
JP_ASSET_NAME_MAP = {
    # ベンチマーク
    '1306.T': '【日】TOPIX連動ETF (1306)',
    # セクター
    '1617.T': '【日】金融 (除く銀行)', '1618.T': '【日】銀行', '1619.T': '【日】建設・資材', '1620.T': '【日】鉄鋼・非鉄',
    '1621.T': '【日】食品', '1622.T': '【日】自動車・輸送機', '1623.T': '【日】エネルギー資源', '1624.T': '【日】商社・卸売',
    '1625.T': '【日】医薬品', '1626.T': '【日】運輸・物流', '1627.T': '【日】不動産', '1628.T': '【日】電機・精密',
    '1629.T': '【日】情報通信・サービス他', '1630.T': '【日】小売', '1631.T': '【日】化学', '1632.T': '【日】機械', '1633.T': '【日】電力・ガス',
    # テーマ・サイズ
    '1308.T': '【日】Large (TOPIX Core30)',
    '1311.T': '【日】Mid (TOPIX Mid400)',
    '1312.T': '【日】Small (TOPIX Small)',
    '2644.T': '【日】半導体 (GX半導体)',
    '1473.T': '【日】グロース (TOPIX Growth)',
    '1474.T': '【日】バリュー (TOPIX Value)'
}

# --- 米国市場の定義 (★ベンチマークをETFに変更) ---
US_BENCHMARK_TICKER = 'SPY' # S&P 500連動ETF
US_SECTOR_TICKERS = ['XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLRE', 'XLB']
US_THEMATIC_TICKERS = ['QQQ', 'MDY', 'IWM', 'SOXX', 'IVW', 'IVE']
US_ASSET_NAME_MAP = {
    # ベンチマーク
    'SPY': '【米】S&P 500連動ETF (SPY)',
    # セクター
    'XLK': '【米】情報技術', 'XLV': '【米】ヘルスケア', 'XLF': '【米】金融', 'XLY': '【米】一般消費財',
    'XLC': '【米】コミュニケーション', 'XLI': '【米】資本財', 'XLP': '【米】生活必需品', 'XLE': '【米】エネルギー',
    'XLU': '【米】公益事業', 'XLRE': '【米】不動産', 'XLB': '【米】素材',
    # テーマ・サイズ
    'QQQ':  '【米】Large (Nasdaq 100)',
    'MDY':  '【米】Mid (S&P MidCap 400)',
    'IWM':  '【米】Small (Russell 2000)',
    'SOXX': '【米】半導体 (iShares SOX)',
    'IVW':  '【米】グロース (S&P 500 Growth)',
    'IVE':  '【米】バリュー (S&P 500 Value)'
}

# 全資産の定義を統合
ALL_JP_TICKERS = list(set([JP_BENCHMARK_TICKER] + JP_SECTOR_TICKERS + JP_THEMATIC_TICKERS))
ALL_US_TICKERS = list(set([US_BENCHMARK_TICKER] + US_SECTOR_TICKERS + US_THEMATIC_TICKERS))
ALL_ASSETS_NAME_MAP = {**JP_ASSET_NAME_MAP, **US_ASSET_NAME_MAP}


# --- 2. 自作の指標計算関数 ---
def calculate_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/length, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 3. データ取得と計算（キャッシュ活用） ---
@st.cache_data(ttl=3600)
def get_data_and_indicators(start_date, end_date, target_tickers):
    strength_dfs = {}
    chart_index = pd.date_range(start=start_date, end=end_date, freq='B')
    fetch_start_date = start_date - pd.DateOffset(days=60)

    # --- 全てのデータをYahoo Financeから一括で取得 ---
    try:
        df_daily_full = yf.download(
            target_tickers,
            start=fetch_start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            timeout=60
        )
    except Exception as e:
        st.error(f"Yahoo Financeからのデータ取得中にエラーが発生しました: {e}")
        return None, None

    if df_daily_full.empty:
        st.error("データを取得できませんでした。")
        return None, None

    # ティッカーが1つの場合でもMultiIndexに変換
    if not isinstance(df_daily_full.columns, pd.MultiIndex):
        df_daily_full.columns = pd.MultiIndex.from_product([df_daily_full.columns, target_tickers])
        
    df_daily_chart = df_daily_full.loc[start_date:end_date].copy()
    
    # --- 指標計算 ---
    try:
        close_prices_full = df_daily_full['Close']
        volume_data_full = df_daily_full['Volume']
        all_rsi_series = [calculate_rsi(close_prices_full[ticker]).rename(ticker) for ticker in target_tickers if ticker in close_prices_full]
        if all_rsi_series:
            strength_dfs['RSI (日足14)'] = pd.concat(all_rsi_series, axis=1).reindex(chart_index, method='ffill')

        all_volume_series = []
        for ticker in target_tickers:
            if ticker in volume_data_full and volume_data_full[ticker].notna().any():
                volume_ma20 = volume_data_full[ticker].rolling(window=20).mean()
                volume_surge = (volume_data_full[ticker] / volume_ma20) * 100
                all_volume_series.append(volume_surge.rename(ticker))
        if all_volume_series:
            volume_df = pd.concat(all_volume_series, axis=1)
            volume_clipped = np.clip(volume_df, 50, 250)
            volume_normalized = (volume_clipped - 50) / 200 * 100
            strength_dfs['出来高急増率(日足20)'] = volume_normalized.reindex(chart_index, method='ffill')
    except Exception as e:
        st.warning(f"日足指標の計算中にエラーが発生しました: {e}")

    try:
        df_intraday = yf.download(target_tickers, start=start_date, end=end_date, interval='5m', group_by='ticker', progress=False, timeout=120)
        if not df_intraday.empty and isinstance(df_intraday.columns, pd.MultiIndex):
            daily_results = []
            for ticker in target_tickers:
                if ticker in df_intraday.columns:
                    ticker_df = df_intraday[ticker].copy().dropna()
                    if not ticker_df.empty:
                        for date, df_day in ticker_df.groupby(lambda x: x.date()):
                            total_intervals = len(df_day)
                            if total_intervals < 1: continue
                            df_day['TP'] = (df_day['High'] + df_day['Low'] + df_day['Close']) / 3
                            df_day['TPxV'] = df_day['TP'] * df_day['Volume']
                            df_day['VWAP'] = df_day['TPxV'].cumsum() / df_day['Volume'].cumsum()
                            df_day['Std'] = df_day['TP'].expanding().std().fillna(0)
                            daily_results.append({'Date': pd.to_datetime(date), 'Ticker': ticker, 'VWAP +1σ維持率(5分足)': ((df_day['Low'] >= (df_day['VWAP'] + df_day['Std'])).sum() / total_intervals) * 100, 'VWAP 0σ維持率(5分足)': ((df_day['Low'] >= df_day['VWAP']).sum() / total_intervals) * 100, 'VWAP -1σ維持率(5分足)': ((df_day['Low'] >= (df_day['VWAP'] - df_day['Std'])).sum() / total_intervals) * 100})
            if daily_results:
                df_vwap_results = pd.DataFrame(daily_results)
                for metric in ['VWAP +1σ維持率(5分足)', 'VWAP 0σ維持率(5分足)', 'VWAP -1σ維持率(5分足)']:
                    strength_dfs[metric] = df_vwap_results.pivot(index='Date', columns='Ticker', values=metric).reindex(chart_index, method='ffill')
    except Exception as e:
        st.warning(f"日中足VWAP指標の計算に失敗しました: {e}")
        
    close_prices_chart = df_daily_chart['Close']
    valid_tickers = [t for t in target_tickers if t in close_prices_chart.columns and close_prices_chart[t].notna().sum() > 1]
    if not valid_tickers:
        st.error("選択された期間に有効な価格データを持つ銘柄がありません。")
        return None, None
    
    close_prices_valid = close_prices_chart[valid_tickers]
    return close_prices_valid, strength_dfs


# --- 4. グラフ描画関数 ---
def create_chart(performance_df, strength_dfs, final_absolute_performance,
                 selected_metric, selected_tickers, chart_title, y_label, baseline,
                 all_tickers_in_market, month_separator_date=None):
    fig, ax = plt.subplots(figsize=(16, 9))
    
    cmap = plt.get_cmap('nipy_spectral', len(all_tickers_in_market))
    ticker_colors = {ticker: cmap(i) for i, ticker in enumerate(all_tickers_in_market)}
    
    strength_df = strength_dfs.get(selected_metric)
    sorted_for_legend = final_absolute_performance.index

    for ticker in sorted_for_legend:
        if ticker not in selected_tickers or ticker not in performance_df.columns: continue
        
        perf_series = performance_df[ticker]
        for j in range(len(perf_series) - 1):
            d_start, d_end = perf_series.index[j], perf_series.index[j+1]
            y_start, y_end = perf_series.iloc[j], perf_series.iloc[j+1]
            
            alpha = 0.6
            if strength_df is not None and not strength_df.empty and ticker in strength_df.columns:
                try:
                    strength_raw = strength_df.loc[d_end, ticker]
                    if pd.isna(strength_raw): strength_raw = 50
                    final_strength = abs(strength_raw - 50) * 2 if (selected_metric and 'RSI' in selected_metric) else strength_raw
                    alpha = 0.15 + (0.85 * (np.clip(final_strength, 0, 100) / 100))
                except (KeyError, IndexError):
                    alpha = 0.15
            
            ax.plot([d_start, d_end], [y_start, y_end], color=ticker_colors.get(ticker, 'gray'), linewidth=2.5, alpha=alpha, zorder=2)

    last_date = performance_df.index[-1]
    for i, ticker in enumerate(sorted_for_legend):
        if ticker in selected_tickers and ticker in performance_df.columns:
            color = ticker_colors.get(ticker, 'gray')
            ax.text(last_date + pd.DateOffset(days=1), performance_df[ticker].iloc[-1], f' {i+1}', color=color, fontsize=10, fontweight='bold', va='center', zorder=3)

    ax.set_title(chart_title, fontsize=16)
    ax.set_ylabel(y_label)
    ax.set_xlabel('日付（線の濃さは選択した指標の強度を示す）')
    ax.grid(True, linestyle='--', alpha=0.6, zorder=1)
    ax.axhline(baseline, color='black', linestyle='--', zorder=1)
    
    chart_start_date = performance_df.index[0]
    chart_end_date = performance_df.index[-1]

    us_sq_dates = pd.date_range(start=chart_start_date, end=chart_end_date, freq='WOM-3FRI')
    for sq_date in us_sq_dates: ax.axvline(x=sq_date, color='red', linestyle='--', linewidth=1.5, zorder=5)

    jp_sq_dates = pd.date_range(start=chart_start_date, end=chart_end_date, freq='WOM-2FRI')
    for sq_date in jp_sq_dates: ax.axvline(x=sq_date, color='blue', linestyle='--', linewidth=1.5, zorder=5)
    
    if month_separator_date: ax.axvline(x=month_separator_date, color='gray', linestyle=':', linewidth=2, zorder=5)

    legend_elements = [Line2D([0], [0], color=ticker_colors.get(ticker, 'gray'), lw=4, label=f"{i+1}. {ALL_ASSETS_NAME_MAP.get(ticker, ticker)} ({ticker})") for i, ticker in enumerate(sorted_for_legend) if ticker in selected_tickers]
    legend_elements.append(Line2D([0], [0], color='red', linestyle='--', lw=1.5, label='米国SQ日 (第3金曜)'))
    legend_elements.append(Line2D([0], [0], color='blue', linestyle='--', lw=1.5, label='日本SQ日 (第2金曜)'))
    if month_separator_date: legend_elements.append(Line2D([0], [0], color='gray', linestyle=':', lw=2, label='月の区切り'))

    ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', title="凡例（絶対パフォーマンス順）")
    fig.tight_layout(rect=[0, 0, 0.85, 1])
    return fig


# --- 5. Streamlit UIとメイン処理 ---
st.set_page_config(layout="wide")
st.title('日米セクター＆テーマ別 パフォーマンス分析ツール')

st.sidebar.header('表示設定')

market_selection = st.sidebar.radio('市場を選択', ('日本', '米国', '日米比較'), index=0, key='market_selection')

display_mode = st.sidebar.radio(
    '表示モード',
    ('絶対パフォーマンス', '相対パフォーマンス'),
    index=0,
    help="絶対: 各銘柄の値動き率。相対: 市場平均連動ETFに対する強さ・弱さ。"
)
if market_selection == '日米比較' and display_mode == '相対パフォーマンス':
    st.sidebar.warning('日米比較モードでは、相対パフォーマンス表示は利用できません。')
    display_mode = '絶対パフォーマンス'

period_option = st.sidebar.selectbox('表示期間を選択', ('先月から今日まで', '今月', '年初来', '過去1年間', 'カスタム'), index=0)
today = pd.Timestamp.today().normalize()
month_separator_date = None

if period_option == '先月から今日まで':
    start_of_this_month = today.replace(day=1)
    start_date = start_of_this_month - pd.DateOffset(months=1)
    end_date = today
    month_separator_date = start_of_this_month
    title_period_text = "先月から今日まで"
elif period_option == '今月':
    start_date = today.replace(day=1)
    end_date = today
    title_period_text = "今月"
elif period_option == '年初来':
    start_date = today.replace(day=1, month=1)
    end_date = today
    title_period_text = "年初来"
elif period_option == '過去1年間':
    start_date = today - pd.DateOffset(years=1)
    end_date = today
    title_period_text = "過去1年間"
else:
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input('開始日', today - pd.DateOffset(months=1))
    end_date = col2.date_input('終了日', today)
    title_period_text = f"{pd.to_datetime(start_date).strftime('%Y/%m/%d')} - {pd.to_datetime(end_date).strftime('%Y/%m/%d')}"

if start_date >= end_date:
    st.error("エラー: 開始日は終了日より前に設定してください。")
else:
    if market_selection == '日本':
        target_tickers = ALL_JP_TICKERS
        benchmark_ticker = JP_BENCHMARK_TICKER
    elif market_selection == '米国':
        target_tickers = ALL_US_TICKERS
        benchmark_ticker = US_BENCHMARK_TICKER
    else:
        target_tickers = ALL_JP_TICKERS + ALL_US_TICKERS
        benchmark_ticker = None

    with st.spinner('データを取得・計算中です...'):
        close_prices, strength_dfs = get_data_and_indicators(pd.to_datetime(start_date), pd.to_datetime(end_date), target_tickers)

    if close_prices is not None and not close_prices.empty:
        absolute_cumulative_returns = (1 + close_prices.pct_change().fillna(0)).cumprod() - 1
        final_absolute_performance = absolute_cumulative_returns.iloc[-1].sort_values(ascending=False)
        sorted_tickers_by_abs = final_absolute_performance.index.tolist()

        chart_title_suffix = f"（{title_period_text}）"
        if display_mode == '相対パフォーマンス' and benchmark_ticker:
            if benchmark_ticker in close_prices.columns:
                benchmark_perf = absolute_cumulative_returns[benchmark_ticker] + 1
                performance_to_plot = (absolute_cumulative_returns + 1).divide(benchmark_perf, axis=0)
                chart_title = f'{market_selection}市場 相対パフォーマンス {chart_title_suffix}'
                y_label = f'市場平均 ({ALL_ASSETS_NAME_MAP.get(benchmark_ticker, benchmark_ticker)}) 比'
                baseline = 1.0
            else:
                st.error(f'ベンチマーク({benchmark_ticker})のデータ取得に失敗したため、絶対パフォーマンスを表示します。')
                display_mode = '絶対パフォーマンス'
        
        if display_mode == '絶対パフォーマンス':
             performance_to_plot = absolute_cumulative_returns * 100
             chart_title = f'{market_selection}市場 絶対パフォーマンス {chart_title_suffix}'
             y_label = '累積リターン (%)'
             baseline = 0.0

        metric_labels = list(strength_dfs.keys())
        if not metric_labels:
            selected_metric = None
        else:
            selected_metric = st.sidebar.radio('線の濃さに反映する指標', metric_labels, index=0)
        
        all_labels = [f"{i+1}. {ALL_ASSETS_NAME_MAP.get(t, t)} ({t})" for i, t in enumerate(sorted_tickers_by_abs)]
        
        if 'selected_tickers' not in st.session_state or 'market_selection_memory' not in st.session_state or st.session_state.market_selection_memory != market_selection:
            st.session_state.selected_tickers = sorted_tickers_by_abs
            st.session_state.market_selection_memory = market_selection

        st.sidebar.write("---")
        st.sidebar.write("**表示銘柄の一括選択**")
        
        cols = st.sidebar.columns(2)
        if cols[0].button('米国のみ', use_container_width=True):
            st.session_state.selected_tickers = [t for t in sorted_tickers_by_abs if t in ALL_US_TICKERS]
        if cols[1].button('日本のみ', use_container_width=True):
            st.session_state.selected_tickers = [t for t in sorted_tickers_by_abs if t in ALL_JP_TICKERS]
        
        cols = st.sidebar.columns(2)
        if cols[0].button('すべて選択', use_container_width=True):
            st.session_state.selected_tickers = sorted_tickers_by_abs
        if cols[1].button('すべて解除', use_container_width=True):
            st.session_state.selected_tickers = []
        
        tickers_to_select = st.session_state.get('selected_tickers', [])
        default_labels = [label for label in all_labels if label.split('(')[-1].replace(')', '') in tickers_to_select]

        selected_labels = st.sidebar.multiselect(
            '**表示する銘柄（絶対パフォーマンス順）**', 
            options=all_labels, 
            default=default_labels
        )
        
        current_selected_tickers = [label.split('(')[-1].replace(')', '') for label in selected_labels]
        st.session_state.selected_tickers = current_selected_tickers
        
        st.header(chart_title)
        chart_fig = create_chart(
            performance_to_plot, strength_dfs, final_absolute_performance,
            selected_metric, current_selected_tickers,
            chart_title, y_label, baseline,
            target_tickers, month_separator_date
        )
        st.pyplot(chart_fig)
        
        st.header('パフォーマンスランキング（絶対リターン基準）')
        st.markdown(f"**期間:** {title_period_text}")
        perf_df = final_absolute_performance.to_frame(name='累積リターン')
        perf_df['累積リターン'] = perf_df['累積リターン'].apply(lambda x: f"{x:.2%}")
        perf_df['銘柄名'] = [ALL_ASSETS_NAME_MAP.get(idx, idx) for idx in perf_df.index]
        perf_df = perf_df.reindex(columns=['銘柄名', '累積リターン'])
        st.dataframe(perf_df.loc[[t for t in sorted_tickers_by_abs if t in current_selected_tickers]], use_container_width=True)
        
        if selected_metric and strength_dfs.get(selected_metric) is not None:
            st.header(f'指標データ: {selected_metric}')
            strength_df_to_display = strength_dfs.get(selected_metric)
            if not strength_df_to_display.empty:
                display_df = strength_df_to_display.reindex(absolute_cumulative_returns.index).dropna(how='all', axis=0).copy()
                display_df = display_df[[ticker for ticker in sorted_tickers_by_abs if ticker in current_selected_tickers]]
                display_df.columns = [f"{ALL_ASSETS_NAME_MAP.get(c, c)} ({c})" for c in display_df.columns]
                st.dataframe(display_df.sort_index(ascending=False).style.format("{:.2f}", na_rep="-"))
    else:
        st.info("指定された期間のデータを取得できませんでした。期間を変更するか、時間を置いてから再度お試しください。")
