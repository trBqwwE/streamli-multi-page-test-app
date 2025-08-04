import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import time
import warnings

# --- 1. 定数と共通設定 (★ここを拡張) ---
warnings.filterwarnings('ignore', category=UserWarning)
try:
    plt.rcParams['font.family'] = 'IPAGothic'
except RuntimeError:
    st.warning("日本語フォント（IPAGothic）が見つかりません。正しく表示されない可能性があります。")
plt.rcParams['axes.unicode_minus'] = False

# --- 日本市場の定義 ---
JP_BENCHMARK_TICKER = '^TPX' # TOPIX
JP_SECTOR_TICKERS = [
    '1617.T', '1618.T', '1619.T', '1620.T', '1621.T', '1622.T', '1623.T', '1624.T',
    '1625.T', '1626.T', '1627.T', '1628.T', '1629.T', '1630.T', '1631.T', '1632.T', '1633.T'
]
JP_THEMATIC_TICKERS = ['1308.T', '1311.T', '1312.T', '2644.T', '1473.T', '1474.T']
JP_ASSET_NAME_MAP = {
    # ベンチマーク
    '^TPX': '【日】TOPIX (市場平均)',
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

# --- 米国市場の定義 ---
US_BENCHMARK_TICKER = '^GSPC' # S&P 500
US_SECTOR_TICKERS = ['XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLRE', 'XLB']
US_THEMATIC_TICKERS = ['QQQ', 'MDY', 'IWM', 'SOXX', 'IVW', 'IVE']
US_ASSET_NAME_MAP = {
    # ベンチマーク
    '^GSPC': '【米】S&P 500 (市場平均)',
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
ALL_JP_TICKERS = [JP_BENCHMARK_TICKER] + JP_SECTOR_TICKERS + JP_THEMATIC_TICKERS
ALL_US_TICKERS = [US_BENCHMARK_TICKER] + US_SECTOR_TICKERS + US_THEMATIC_TICKERS
ALL_ASSETS_NAME_MAP = {**JP_ASSET_NAME_MAP, **US_ASSET_NAME_MAP}

# --- 2. 自作の指標計算関数 --- (変更なし)
def calculate_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/length, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 3. データ取得と計算（キャッシュ活用） --- (★ここを修正)
@st.cache_data(ttl=3600)
def get_data_and_indicators(start_date, end_date, target_tickers):
    import yfinance as yf

    strength_dfs = {}
    chart_index = pd.date_range(start=start_date, end=end_date, freq='B')

    try:
        df_daily_full = yf.download(
            target_tickers,
            start=start_date - pd.DateOffset(days=60),
            end=end_date,
            auto_adjust=True,
            progress=False,
            timeout=60
        )
        if df_daily_full.empty:
            st.error("日足データの取得に失敗しました。")
            return None
        if not isinstance(df_daily_full.columns, pd.MultiIndex):
            df_daily_full.columns = pd.MultiIndex.from_product([df_daily_full.columns, target_tickers])

    except Exception as e:
        st.error(f"日足データの取得中に予期せぬエラーが発生しました: {e}")
        return None

    df_daily_chart = df_daily_full.loc[start_date:end_date].copy()

    # (日足指標計算ロジックは変更なし)
    try:
        close_prices = df_daily_full['Close']
        volume_data = df_daily_full['Volume']
        all_rsi_series = [calculate_rsi(close_prices[ticker]).rename(ticker) for ticker in target_tickers if ticker in close_prices]
        if all_rsi_series:
            strength_dfs['RSI (日足14)'] = pd.concat(all_rsi_series, axis=1).reindex(chart_index, method='ffill')

        all_volume_series = []
        for ticker in target_tickers:
            if ticker in volume_data and volume_data[ticker].notna().any():
                volume_ma20 = volume_data[ticker].rolling(window=20).mean()
                volume_surge = (volume_data[ticker] / volume_ma20) * 100
                all_volume_series.append(volume_surge.rename(ticker))
        if all_volume_series:
            volume_df = pd.concat(all_volume_series, axis=1)
            volume_clipped = np.clip(volume_df, 50, 250)
            volume_normalized = (volume_clipped - 50) / 200 * 100
            strength_dfs['出来高急増率(日足20)'] = volume_normalized.reindex(chart_index, method='ffill')
    except Exception as e:
        st.warning(f"日足指標の計算中にエラーが発生しました: {e}")

    # (日中足VWAP指標計算ロジックは変更なし)
    try:
        df_intraday = yf.download(
            target_tickers,
            start=start_date,
            end=end_date,
            interval='5m',
            group_by='ticker',
            progress=False,
            timeout=120
        )
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

    # --- ここからが修正箇所 ---
    # 祝日の違いによるデータ欠損に対応するため、検証ロジックを変更
    # 期間中に2日以上の有効な価格データを持つティッカーのみを対象とする
    close_prices_chart = df_daily_chart['Close']
    valid_tickers = close_prices_chart.columns[close_prices_chart.notna().sum() > 1]

    if not valid_tickers.any(): # .any() を使ってティッカーが一つでも存在するか確認
        st.error("選択された期間に有効な価格データを持つセクターがありません。（2日以上のデータを持つセクターが見つかりません）")
        return None

    # 有効なティッカーのデータのみを使用
    close_prices_valid = close_prices_chart[valid_tickers]

    # 変化率を計算し、NaN（祝日などで発生）を0で埋める
    # これにより、データがない日はリターン0%として扱われ、累積計算が継続される
    cumulative_returns = (1 + close_prices_valid.pct_change().fillna(0)).cumprod() - 1
    # --- 修正箇所ここまで ---

    final_performance = cumulative_returns.iloc[-1].sort_values(ascending=False)
    sorted_tickers = final_performance.index.tolist()

    return cumulative_returns, strength_dfs, final_performance, sorted_tickers


# --- 4. グラフ描画関数 --- (変更なし)
def create_chart(performance_df, strength_dfs, final_performance, sorted_tickers,
                 selected_metric, selected_tickers, chart_title, y_label, baseline,
                 all_tickers_for_market, month_separator_date=None):
    fig, ax = plt.subplots(figsize=(16, 9))
    
    cmap = plt.get_cmap('nipy_spectral', len(all_tickers_for_market))
    ticker_colors = {ticker: cmap(i) for i, ticker in enumerate(all_tickers_for_market)}
    
    # 凡例用のソート順は絶対パフォーマンス基準
    sorted_for_legend = final_performance.index

    # グラフ描画
    for ticker in sorted_for_legend:
        if ticker not in selected_tickers or ticker not in performance_df.columns: continue
        # (描画ロジックは変更なし)
        # ...
        ax.plot(performance_df.index, performance_df[ticker], color=ticker_colors.get(ticker, 'gray'), linewidth=2.5, zorder=2) # 簡略化のためalphaを除外

    last_date = performance_df.index[-1]
    for i, ticker in enumerate(sorted_for_legend):
        if ticker in selected_tickers and ticker in performance_df.columns:
            color = ticker_colors.get(ticker, 'gray')
            ax.text(last_date + pd.DateOffset(days=1), performance_df[ticker].iloc[-1], f' {i+1}', color=color, fontsize=10, fontweight='bold', va='center', zorder=3)

    ax.set_title(chart_title, fontsize=16)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle='--', alpha=0.6, zorder=1)
    # 基準線を動的に設定
    ax.axhline(baseline, color='black', linestyle='--', zorder=1)

    chart_start_date = cumulative_returns.index[0]
    chart_end_date = cumulative_returns.index[-1]

    us_sq_dates = pd.date_range(start=chart_start_date, end=chart_end_date, freq='WOM-3FRI')
    for sq_date in us_sq_dates:
        ax.axvline(x=sq_date, color='red', linestyle='--', linewidth=1.5, zorder=5)

    jp_sq_dates = pd.date_range(start=chart_start_date, end=chart_end_date, freq='WOM-2FRI')
    for sq_date in jp_sq_dates:
        ax.axvline(x=sq_date, color='blue', linestyle='--', linewidth=1.5, zorder=5)
    
    if month_separator_date:
        ax.axvline(x=month_separator_date, color='gray', linestyle=':', linewidth=2, zorder=5)

    legend_elements = [Line2D([0], [0], color=ticker_colors.get(ticker, 'gray'), lw=4, label=f"{i+1}. {ALL_ASSETS_NAME_MAP.get(ticker, ticker)} ({ticker})") for i, ticker in enumerate(sorted_for_legend) if ticker in selected_tickers]
    legend_elements.append(Line2D([0], [0], color='red', linestyle='--', lw=1.5, label='米国SQ日 (第3金曜)'))
    legend_elements.append(Line2D([0], [0], color='blue', linestyle='--', lw=1.5, label='日本SQ日 (第2金曜)'))
    if month_separator_date: legend_elements.append(Line2D([0], [0], color='gray', linestyle=':', lw=2, label='月の区切り'))

    ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', title="凡例（絶対パフォーマンス順）")
    fig.tight_layout(rect=[0, 0, 0.85, 1])
    return fig


# --- 5. Streamlit UIとメイン処理 --- (★ここから下を全面的に修正)
st.set_page_config(layout="wide")
st.title('日米セクター＆テーマ別 パフォーマンス分析ツール')

st.sidebar.header('表示設定')

# --- UI設定 ---
market_selection = st.sidebar.radio('市場を選択', ('日本', '米国', '日米比較'), index=0, key='market_selection')

display_mode = st.sidebar.radio(
    '表示モード', 
    ('絶対パフォーマンス', '相対パフォーマンス'), 
    index=0,
    help="絶対: 各銘柄の値動き率。相対: 市場平均(TOPIX/S&P500)に対する強さ・弱さ。"
)
# 日米比較モードでは相対表示を無効化
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
    # --- 分析対象ティッカーの決定 ---
    if market_selection == '日本':
        target_tickers = list(set(ALL_JP_TICKERS))
        benchmark_ticker = JP_BENCHMARK_TICKER
    elif market_selection == '米国':
        target_tickers = list(set(ALL_US_TICKERS))
        benchmark_ticker = US_BENCHMARK_TICKER
    else: # 日米比較
        target_tickers = list(set(ALL_JP_TICKERS + ALL_US_TICKERS))
        benchmark_ticker = None

    with st.spinner('データを取得・計算中です...'):
        close_prices, strength_dfs = get_data_and_indicators(pd.to_datetime(start_date), pd.to_datetime(end_date), target_tickers)

    if close_prices is not None:
        # --- パフォーマンス計算 ---
        # 常に絶対パフォーマンスを計算（ランキングと相対化の基準として使用）
        absolute_cumulative_returns = (1 + close_prices.pct_change().fillna(0)).cumprod() - 1
        final_absolute_performance = absolute_cumulative_returns.iloc[-1].sort_values(ascending=False)
        sorted_tickers_by_abs = final_absolute_performance.index.tolist()

        # 表示モードに応じてプロットするデータとチャート設定を決定
        chart_title_suffix = f"（{title_period_text}）"
        if display_mode == '相対パフォーマンス' and benchmark_ticker:
            if benchmark_ticker in absolute_cumulative_returns.columns:
                # ベンチマークの累積リターン（0基点）に1を足して、1基点のパフォーマンスにする
                benchmark_perf = absolute_cumulative_returns[benchmark_ticker] + 1
                # 各資産のパフォーマンス（1基点）をベンチマークのパフォーマンスで割る
                performance_to_plot = (absolute_cumulative_returns + 1).divide(benchmark_perf, axis=0)
                
                chart_title = f'{market_selection}市場 相対パフォーマンス {chart_title_suffix}'
                y_label = f'市場平均 ({ALL_ASSETS_NAME_MAP[benchmark_ticker]}) 比'
                baseline = 1.0
            else:
                st.error(f'ベンチマーク({benchmark_ticker})のデータが取得できませんでした。絶対パフォーマンスを表示します。')
                display_mode = '絶対パフォーマンス' # fallback
        
        # display_modeが絶対パフォーマンスの場合（fallback含む）
        if display_mode == '絶対パフォーマンス':
             performance_to_plot = absolute_cumulative_returns * 100 # %表示に変換
             chart_title = f'{market_selection}市場 絶対パフォーマンス {chart_title_suffix}'
             y_label = '累積リターン (%)'
             baseline = 0.0

        # --- UI（銘柄選択） ---
        all_labels = [f"{i+1}. {ALL_ASSETS_NAME_MAP.get(t, t)} ({t})" for i, t in enumerate(sorted_tickers_by_abs)]
        
        if 'selected_labels' not in st.session_state or 'market_selection_memory' not in st.session_state or st.session_state.market_selection_memory != market_selection:
            st.session_state.selected_labels = all_labels
            st.session_state.market_selection_memory = market_selection

        st.sidebar.write("---")
        st.sidebar.write("**表示銘柄の一括選択**")
        
        cols = st.sidebar.columns(2)
        if cols[0].button('米国のみ', use_container_width=True):
            st.session_state.selected_labels = [l for l in all_labels if l.split('(')[-1].replace(')', '') in ALL_US_TICKERS]
        if cols[1].button('日本のみ', use_container_width=True):
            st.session_state.selected_labels = [l for l in all_labels if l.split('(')[-1].replace(')', '') in ALL_JP_TICKERS]
        
        cols = st.sidebar.columns(2)
        if cols[0].button('すべて選択', use_container_width=True):
            st.session_state.selected_labels = all_labels
        if cols[1].button('すべて解除', use_container_width=True):
            st.session_state.selected_labels = []

        selected_labels = st.sidebar.multiselect(
            '**表示する銘柄（絶対パフォーマンス順）**', 
            options=all_labels, 
            default=st.session_state.selected_labels
        )
        if selected_labels != st.session_state.selected_labels:
             st.session_state.selected_labels = selected_labels
        
        selected_tickers = [label.split('(')[-1].replace(')', '') for label in selected_labels]

        # --- グラフとテーブル表示 ---
        st.header(chart_title)
        chart_fig = create_chart(
            performance_to_plot, strength_dfs, final_absolute_performance,
            None, selected_tickers, # selected_metricは今回未実装
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
        st.dataframe(perf_df, use_container_width=True)
        
    else:
        st.info("指定された期間のデータを取得できませんでした。期間を変更するか、時間を置いてから再度お試しください。")
