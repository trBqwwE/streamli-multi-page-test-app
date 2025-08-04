
import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas_ta as ta
import numpy as np
import time

# --- 1. 共通設定 (Streamlit用に調整) ---
# Matplotlibのフォント設定
plt.rcParams['font.family'] = 'Meiryo'
plt.rcParams['axes.unicode_minus'] = False

# 定数
US_SECTOR_TICKERS = ['XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLRE', 'XLB']
SECTOR_NAME_MAP = {
    'XLK': '情報技術', 'XLV': 'ヘルスケア', 'XLF': '金融', 'XLY': '一般消費財',
    'XLC': 'コミュニケーション', 'XLI': '資本財', 'XLP': '生活必需品', 'XLE': 'エネルギー',
    'XLU': '公益事業', 'XLRE': '不動産', 'XLB': '素材'
}

# --- 2. データ取得・指標計算関数 (キャッシュ機能付き) ---
@st.cache_data(ttl=3600) # 1時間キャッシュ
def get_data_and_indicators(start_date, end_date):
    """
    指定された期間の株価データを取得し、各種指標を計算する関数。
    """
    st.info(f"データ取得と指標計算を実行中... ({start_date.date()} to {end_date.date()})")
    strength_dfs = {}

    # 日足データ取得 (計算用に60日前から取得)
    daily_start_long = start_date - pd.DateOffset(days=60)
    df_daily_full = yf.download(US_SECTOR_TICKERS, start=daily_start_long, end=end_date, auto_adjust=True, progress=False)
    if df_daily_full.empty:
        st.error("日足データの取得に失敗しました。")
        return None

    df_daily_chart = df_daily_full.loc[start_date:end_date].copy()
    chart_index = df_daily_chart.index

    # 日足ベースの指標計算 (RSI, 出来高急増率)
    try:
        all_rsi_series = []
        all_volume_series = []
        close_prices = df_daily_full['Close']
        volume_data = df_daily_full['Volume']
        for ticker in close_prices.columns:
            rsi_series = ta.rsi(close_prices[ticker], length=14); rsi_series.name = ticker
            all_rsi_series.append(rsi_series)
            volume_ma20 = volume_data[ticker].rolling(window=20).mean()
            volume_surge = (volume_data[ticker] / volume_ma20) * 100; volume_surge.name = ticker
            all_volume_series.append(volume_surge)

        if all_rsi_series:
            rsi_df = pd.concat(all_rsi_series, axis=1)
            strength_dfs['RSI (日足14)'] = rsi_df.reindex(chart_index)
        if all_volume_series:
            volume_df = pd.concat(all_volume_series, axis=1)
            volume_clipped = np.clip(volume_df, 50, 250)
            volume_normalized = (volume_clipped - 50) / 200 * 100
            strength_dfs['出来高急増率(日足20)'] = volume_normalized.reindex(chart_index)
    except Exception as e:
        st.warning(f"日足指標の計算中にエラーが発生しました: {e}")

    # 5分足ベースの指標計算 (VWAP維持率)
    try:
        df_intraday = yf.download(US_SECTOR_TICKERS, start=start_date, end=end_date, interval='5m', group_by='ticker', progress=False, timeout=60)
        if not df_intraday.empty and not df_intraday.isnull().all().all():
            daily_results = []
            for ticker in US_SECTOR_TICKERS:
                if ticker in df_intraday.columns and not df_intraday[ticker].isnull().all().all():
                    for date, df_day in df_intraday[ticker].copy().dropna().groupby(lambda x: x.date()):
                        total_intervals = len(df_day)
                        if total_intervals < 1: continue
                        df_day['TP'] = (df_day['High'] + df_day['Low'] + df_day['Close']) / 3
                        df_day['TPxV'] = df_day['TP'] * df_day['Volume']
                        df_day['VWAP'] = df_day['TPxV'].cumsum() / df_day['Volume'].cumsum()
                        df_day['Std'] = df_day['TP'].expanding().std().fillna(0)
                        daily_results.append({
                            'Date': pd.to_datetime(date), 'Ticker': ticker,
                            'VWAP +1σ維持率(5分足)': ((df_day['Low'] >= (df_day['VWAP'] + df_day['Std'])).sum() / total_intervals) * 100,
                            'VWAP  0σ維持率(5分足)': ((df_day['Low'] >= df_day['VWAP']).sum() / total_intervals) * 100,
                            'VWAP -1σ維持率(5分足)': ((df_day['Low'] >= (df_day['VWAP'] - df_day['Std'])).sum() / total_intervals) * 100
                        })
            if daily_results:
                df_vwap_results = pd.DataFrame(daily_results)
                for metric in ['VWAP +1σ維持率(5分足)', 'VWAP  0σ維持率(5分足)', 'VWAP -1σ維持率(5分足)']:
                    strength_dfs[metric] = df_vwap_results.pivot(index='Date', columns='Ticker', values=metric).reindex(chart_index)
    except Exception as e:
        st.warning(f"日中足VWAP指標の計算に失敗しました: {e}")

    if df_daily_chart.empty:
        return None

    # 累積リターンの計算
    cumulative_returns = (1 + df_daily_chart['Close'].pct_change()).cumprod() - 1
    cumulative_returns = cumulative_returns.fillna(0)
    final_performance = cumulative_returns.iloc[-1].sort_values(ascending=False)
    sorted_tickers = final_performance.index

    return cumulative_returns, strength_dfs, final_performance, sorted_tickers

# --- 3. グラフ描画関数 ---
def create_chart(cumulative_returns, strength_dfs, final_performance, sorted_tickers,
                 selected_metric, selected_tickers, title_period_text, month_separator_date=None):
    """
    Streamlitの入力に基づいてインタラクティブなチャートを描画する関数。
    """
    fig, ax = plt.subplots(figsize=(16, 9))

    colors = plt.cm.get_cmap('tab10').colors
    ticker_colors = {ticker: colors[i % len(colors)] for i, ticker in enumerate(US_SECTOR_TICKERS)}

    strength_df = strength_dfs.get(selected_metric)

    # 各セクターの累積リターンをプロット
    for ticker in sorted_tickers:
        if ticker not in selected_tickers:
            continue

        for j in range(len(cumulative_returns) - 1):
            d_start, d_end = cumulative_returns.index[j], cumulative_returns.index[j+1]
            y_start, y_end = cumulative_returns[ticker].iloc[j], cumulative_returns[ticker].iloc[j+1]

            # 選択された指標に基づいて線のアルファ値（濃さ）を計算
            alpha = 0.6 # デフォルト値
            if strength_df is not None:
                strength_raw = strength_df.get(ticker, {}).get(d_end, 50) # 該当日にデータがなければ50を仮定
                if pd.isna(strength_raw): strength_raw = 50

                final_strength = 0
                if 'RSI' in selected_metric:
                    final_strength = abs(strength_raw - 50) * 2 # 50から離れるほど濃くする
                else:
                    final_strength = strength_raw # 値が大きいほど濃くする

                # 0-100の範囲に正規化された強度を0.15-1.0のアルファ値に変換
                alpha = 0.15 + (0.85 * (np.clip(final_strength, 0, 100) / 100))

            ax.plot([d_start, d_end], [y_start, y_end], color=ticker_colors[ticker], linewidth=2.5, alpha=alpha, zorder=2)

    # 最後の日に順位ラベルを表示
    last_date = cumulative_returns.index[-1]
    for i, ticker in enumerate(sorted_tickers):
        if ticker in selected_tickers:
            ax.text(last_date, final_performance[ticker], f' {i+1}', color=ticker_colors[ticker], fontsize=10, fontweight='bold', va='center', zorder=3)

    # グラフの装飾
    ax.set_title(f'セクター別累積リターンと各種指標（{title_period_text}）', fontsize=16)
    ax.set_ylabel('累積リターン (%)')
    ax.set_xlabel('日付（線の濃さは選択した指標の強度を示す）')
    ax.grid(True, linestyle='--', alpha=0.6, zorder=1)
    ax.axhline(0, color='black', linestyle='--', zorder=1)

    # SQ日と月の区切り線
    sq_dates = pd.date_range(start=cumulative_returns.index[0], end=cumulative_returns.index[-1], freq='WOM-3FRI')
    for sq_date in sq_dates:
        ax.axvline(x=sq_date, color='red', linestyle='--', linewidth=1.5, zorder=5)
    if month_separator_date:
        ax.axvline(x=month_separator_date, color='gray', linestyle=':', linewidth=2, zorder=5)

    # 凡例の作成
    legend_elements = [Line2D([0], [0], color=ticker_colors[ticker], lw=4, label=f"{i+1}. {SECTOR_NAME_MAP[ticker]} ({ticker})")
                       for i, ticker in enumerate(sorted_tickers) if ticker in selected_tickers]
    legend_elements.append(Line2D([0], [0], color='red', linestyle='--', lw=1.5, label='米国オプションSQ日'))
    if month_separator_date:
        legend_elements.append(Line2D([0], [0], color='gray', linestyle=':', lw=2, label='月の区切り'))

    ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', title="凡例（パフォーマンス順）")
    fig.tight_layout(rect=[0, 0, 0.85, 1]) # 凡例スペースを確保

    return fig

# --- 4. Streamlit アプリケーションのメイン処理 ---
st.set_page_config(layout="wide")
st.title('米国セクター別 パフォーマンス・強度分析')
st.markdown("""
このアプリケーションは、米国の主要11セクターの株価パフォーマンスを視覚化します。
サイドバーのオプションを変更することで、表示期間や分析の切り口をインタラクティブに変更できます。
線の色の濃さは、選択されたテクニカル指標の「強度」を表しています。
""")

# --- サイドバー (操作パネル) ---
st.sidebar.header('表示設定')

# 期間選択
period_option = st.sidebar.selectbox(
    '表示期間を選択',
    ('先月から今日まで', '今月', 'カスタム'),
    index=0
)

today = pd.Timestamp.today().normalize()
start_of_this_month = today.replace(day=1)
start_of_last_month = start_of_this_month - pd.DateOffset(months=1)
month_separator_date = None

if period_option == '先月から今日まで':
    start_date = start_of_last_month
    end_date = today
    month_separator_date = start_of_this_month
    title_period_text = "先月から今日まで"
elif period_option == '今月':
    start_date = start_of_this_month
    end_date = today
    title_period_text = "今月"
else:
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input('開始日', start_of_last_month)
    end_date = col2.date_input('終了日', today)
    title_period_text = f"{pd.to_datetime(start_date).strftime('%Y/%m/%d')} - {pd.to_datetime(end_date).strftime('%Y/%m/%d')}"

# データ取得と計算の実行
data = get_data_and_indicators(pd.to_datetime(start_date), pd.to_datetime(end_date))

if data:
    cumulative_returns, strength_dfs, final_performance, sorted_tickers = data

    # 指標選択
    metric_labels = list(strength_dfs.keys())
    if not metric_labels:
        st.sidebar.warning("利用可能な指標がありません。")
        selected_metric = None
    else:
        selected_metric = st.sidebar.radio(
            '線の濃さに反映する指標',
            metric_labels,
            index=0
        )

    # セクター選択
    sector_labels = [f"{i+1}. {SECTOR_NAME_MAP.get(t, t)} ({t})" for i, t in enumerate(sorted_tickers)]
    selected_labels = st.sidebar.multiselect(
        '表示するセクター（パフォーマンス順）',
        options=sector_labels,
        default=sector_labels
    )
    selected_tickers = [label.split('(')[-1].replace(')', '') for label in selected_labels]

    # --- メインパネル (グラフと情報) ---
    st.header('セクター別 累積リターン')

    # グラフ描画
    chart_fig = create_chart(
        cumulative_returns, strength_dfs, final_performance, sorted_tickers,
        selected_metric, selected_tickers, title_period_text, month_separator_date
    )
    st.pyplot(chart_fig)

    # パフォーマンスランキングの表示
    st.header('パフォーマンスランキング')
    st.markdown(f"**期間:** {title_period_text}")
    
    # パフォーマンスデータを整形して表示
    perf_df = final_performance.to_frame(name='累積リターン')
    perf_df['累積リターン'] = perf_df['累積リターン'].apply(lambda x: f"{x:.2%}")
    perf_df['セクター名'] = [SECTOR_NAME_MAP.get(idx, idx) for idx in perf_df.index]
    perf_df = perf_df[['セクター名', '累積リターン']]
    st.dataframe(perf_df, use_container_width=True)

else:
    st.error("データを表示できませんでした。期間を変更するか、時間を置いてから再度お試しください。")