import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
# pandas_ta はもうインポートしない
import numpy as np
import time
import warnings

# --- 0. Streamlit アプリ設定 ---
st.set_page_config(layout="wide")

# --- 1. 定数と共通設定 ---
warnings.filterwarnings('ignore', category=UserWarning)
try:
    plt.rcParams['font.family'] = 'IPAGothic'
except RuntimeError:
    st.warning("日本語フォント（IPAGothic）が見つかりません。packages.txtが正しく設定されているか確認してください。")
plt.rcParams['axes.unicode_minus'] = False

US_SECTOR_TICKERS = ['XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLRE', 'XLB']
SECTOR_NAME_MAP = {
    'XLK': '情報技術', 'XLV': 'ヘルスケア', 'XLF': '金融', 'XLY': '一般消費財',
    'XLC': 'コミュニケーション', 'XLI': '資本財', 'XLP': '生活必需品', 'XLE': 'エネルギー',
    'XLU': '公益事業', 'XLRE': '不動産', 'XLB': '素材'
}

# --- 2. 自作の指標計算関数 ---
def calculate_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """pandasだけでRSIを計算する関数"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/length, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 3. データ取得と計算（キャッシュ活用） ---
@st.cache_data(ttl=3600)
def get_data_and_indicators(start_date, end_date):
    """
    指定された期間の株価データを取得し、各種指標を計算する関数。
    """
    # 以前のyfinanceデータ取得エラー対策も残しておきます
    import requests
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
    
    try:
        yf.Ticker("MSFT", session=session).history(period="1d")
        time.sleep(0.5)
    except Exception:
        pass

    strength_dfs = {}
    chart_index = pd.date_range(start=start_date, end=end_date, freq='B')

    try:
        df_daily_full = yf.download(US_SECTOR_TICKERS, start=start_date - pd.DateOffset(days=60), end=end_date, auto_adjust=True, progress=False, session=session)
        if df_daily_full.empty:
            st.error("日足データの取得に失敗しました。")
            return None
    except Exception as e:
        st.error(f"データ取得中にエラーが発生しました: {e}")
        return None

    df_daily_chart = df_daily_full.loc[start_date:end_date].copy()

    # --- ここから指標計算を自前のコードに置き換え ---
    try:
        close_prices = df_daily_full['Close']
        volume_data = df_daily_full['Volume']
        
        # (RSI) 自作のRSI関数を使用
        all_rsi_series = [calculate_rsi(close_prices[ticker]).rename(ticker) for ticker in US_SECTOR_TICKERS if ticker in close_prices]
        if all_rsi_series:
            strength_dfs['RSI (日足14)'] = pd.concat(all_rsi_series, axis=1).reindex(chart_index, method='ffill')
        
        # (出来高急増率) これは元々pandasだけで計算していたので変更なし
        all_volume_series = []
        for ticker in US_SECTOR_TICKERS:
            if ticker in volume_data:
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

    # (5分足VWAP) この部分は変更なし
    try:
        df_intraday = yf.download(US_SECTOR_TICKERS, start=start_date, end=end_date, interval='5m', group_by='ticker', progress=False, timeout=60, session=session)
        if not df_intraday.empty and isinstance(df_intraday.columns, pd.MultiIndex):
            # (VWAP計算ロジックは長いので省略...元のコードと同じです)
            daily_results = []
            for ticker in US_SECTOR_TICKERS:
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

    cumulative_returns = (1 + df_daily_chart['Close'].pct_change()).cumprod() - 1
    cumulative_returns = cumulative_returns.fillna(0)
    final_performance = cumulative_returns.iloc[-1].sort_values(ascending=False)
    sorted_tickers = final_performance.index

    return cumulative_returns, strength_dfs, final_performance, sorted_tickers

# --- 4. グラフ描画関数 ---
def create_chart(cumulative_returns, strength_dfs, final_performance, sorted_tickers,
                 selected_metric, selected_tickers, title_period_text, month_separator_date=None):
    fig, ax = plt.subplots(figsize=(16, 9))
    colors = plt.colormaps.get('tab10').colors
    ticker_colors = {ticker: colors[i % len(colors)] for i, ticker in enumerate(US_SECTOR_TICKERS)}
    strength_df = strength_dfs.get(selected_metric)

    for ticker in sorted_tickers:
        if ticker not in selected_tickers: continue
        for j in range(len(cumulative_returns) - 1):
            d_start, d_end = cumulative_returns.index[j], cumulative_returns.index[j+1]
            y_start, y_end = cumulative_returns[ticker].iloc[j], cumulative_returns[ticker].iloc[j+1]
            alpha = 0.6
            if strength_df is not None and not strength_df.empty:
                try:
                    strength_raw = strength_df.loc[d_end, ticker]
                    if pd.isna(strength_raw): strength_raw = 50
                    final_strength = abs(strength_raw - 50) * 2 if 'RSI' in selected_metric else strength_raw
                    alpha = 0.15 + (0.85 * (np.clip(final_strength, 0, 100) / 100))
                except (KeyError, IndexError):
                    alpha = 0.15
            ax.plot([d_start, d_end], [y_start, y_end], color=ticker_colors[ticker], linewidth=2.5, alpha=alpha, zorder=2)

    last_date = cumulative_returns.index[-1]
    for i, ticker in enumerate(sorted_tickers):
        if ticker in selected_tickers:
            ax.text(last_date, final_performance[ticker], f' {i+1}', color=ticker_colors[ticker], fontsize=10, fontweight='bold', va='center', zorder=3)

    ax.set_title(f'セクター別累積リターンと各種指標（{title_period_text}）', fontsize=16)
    ax.set_ylabel('累積リターン (%)')
    ax.set_xlabel('日付（線の濃さは選択した指標の強度を示す）')
    ax.grid(True, linestyle='--', alpha=0.6, zorder=1)
    ax.axhline(0, color='black', linestyle='--', zorder=1)
    sq_dates = pd.date_range(start=cumulative_returns.index[0], end=cumulative_returns.index[-1], freq='WOM-3FRI')
    for sq_date in sq_dates: ax.axvline(x=sq_date, color='red', linestyle='--', linewidth=1.5, zorder=5)
    if month_separator_date: ax.axvline(x=month_separator_date, color='gray', linestyle=':', linewidth=2, zorder=5)
    legend_elements = [Line2D([0], [0], color=ticker_colors[ticker], lw=4, label=f"{i+1}. {SECTOR_NAME_MAP[ticker]} ({ticker})") for i, ticker in enumerate(sorted_tickers) if ticker in selected_tickers]
    legend_elements.append(Line2D([0], [0], color='red', linestyle='--', lw=1.5, label='米国オプションSQ日'))
    if month_separator_date: legend_elements.append(Line2D([0], [0], color='gray', linestyle=':', lw=2, label='月の区切り'))
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', title="凡例（パフォーマンス順）")
    fig.tight_layout(rect=[0, 0, 0.85, 1])
    return fig

# --- 5. Streamlit UIとメイン処理 ---
st.title('米国セクター別 パフォーマンス・強度分析')
st.markdown("...") # 省略

st.sidebar.header('表示設定')
period_option = st.sidebar.selectbox('表示期間を選択', ('先月から今日まで', '今月', '年初来', '過去1年間', 'カスタム'), index=0)
today = pd.Timestamp.today().normalize()
month_separator_date = None

# (期間選択ロジック - 省略...元のコードと同じ)
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
    with st.spinner('データを取得・計算中です...'):
        data = get_data_and_indicators(pd.to_datetime(start_date), pd.to_datetime(end_date))

    if data:
        cumulative_returns, strength_dfs, final_performance, sorted_tickers = data
        metric_labels = list(strength_dfs.keys())
        if not metric_labels:
            st.sidebar.warning("利用可能な指標がありません。")
            selected_metric = None
        else:
            selected_metric = st.sidebar.radio('線の濃さに反映する指標', metric_labels, index=0)
        sector_labels = [f"{i+1}. {SECTOR_NAME_MAP.get(t, t)} ({t})" for i, t in enumerate(sorted_tickers)]
        selected_labels = st.sidebar.multiselect('表示するセクター（パフォーマンス順）', options=sector_labels, default=sector_labels)
        selected_tickers = [label.split('(')[-1].replace(')', '') for label in selected_labels]

        st.header('セクター別 累積リターン')
        chart_fig = create_chart(cumulative_returns, strength_dfs, final_performance, sorted_tickers, selected_metric, selected_tickers, title_period_text, month_separator_date)
        st.pyplot(chart_fig)
        
        st.header('パフォーマンスランキング')
        st.markdown(f"**期間:** {title_period_text}")
        perf_df = final_performance.to_frame(name='累積リターン')
        perf_df['累積リターン'] = perf_df['累積リターン'].apply(lambda x: f"{x:.2%}")
        perf_df['セクター名'] = [SECTOR_NAME_MAP.get(idx, idx) for idx in perf_df.index]
        perf_df = perf_df[['セクター名', '累積リターン']]
        st.dataframe(perf_df, use_container_width=True)
        
        if selected_metric and strength_dfs.get(selected_metric) is not None:
            st.header(f'指標データ: {selected_metric}')
            strength_df = strength_dfs.get(selected_metric)
            if not strength_df.empty:
                display_df = strength_df.reindex(cumulative_returns.index).dropna(how='all').copy()
                display_df.columns = [f"{SECTOR_NAME_MAP.get(c, c)} ({c})" for c in display_df.columns]
                st.dataframe(display_df.sort_index(ascending=False).style.format("{:.2f}", na_rep="-"))
    else:
        st.error("データを表示できませんでした。期間を変更するか、時間を置いてから再度お試しください。")
