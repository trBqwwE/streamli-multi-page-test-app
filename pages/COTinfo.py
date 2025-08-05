import streamlit as st
import cot_reports as cot
import pandas as pd
import datetime
import yfinance as yf


# --------------------------------------------------------------------------
# --- Streamlit ページ設定 ---
# --------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="COTレポート分析スキャナー")

# --------------------------------------------------------------------------
# --- 設定 ---
# --------------------------------------------------------------------------

ASSET_MAP = {
    '090741': 'カナダドル',
    '092741': 'スイスフラン',
    '096742': '英ポンド',
    '097741': '日本円',
    '099741': 'ユーロ',
    '232741': '豪ドル',
    '098662': '米ドル (DXY)',
    '13874+': 'S&P 500',
    '20974+': 'NASDAQ 100',
    '12460+': 'Dow Jones',
    '240743': '日経 225',
    '088691': '金 (Gold)',
    '084691': '銀 (Silver)',
    '06765A': '原油 (WTI)',
    '023391': '天然ガス',
    '043602': '米国10年債',
    '020601': '米国30年債'
}

LOOKBACK_WEEKS = 26
DATA_FRESHNESS_THRESHOLD_DAYS = 9

# 契約サイズと価格取得用ティッカーの定義
CONTRACT_SPECS = {
    # 通貨
    'カナダドル':  {'unit': 100000, 'ticker': 'CADUSD=X', 'currency': 'USD'}, # 1 CADあたりのUSD
    'スイスフラン': {'unit': 125000, 'ticker': 'CHFUSD=X', 'currency': 'USD'}, # 1 CHFあたりのUSD
    '英ポンド':    {'unit': 62500,  'ticker': 'GBPUSD=X', 'currency': 'USD'}, # 1 GBPあたりのUSD
    '日本円':      {'unit': 12500000, 'ticker': 'JPY=X', 'currency': 'JPY_PER_USD'}, # 1 USDあたりのJPY
    'ユーロ':      {'unit': 125000, 'ticker': 'EURUSD=X', 'currency': 'USD'}, # 1 EURあたりのUSD
    '豪ドル':      {'unit': 100000, 'ticker': 'AUDUSD=X', 'currency': 'USD'}, # 1 AUDあたりのUSD
    '米ドル (DXY)':{'unit': 1000,   'ticker': 'DX-Y.NYB', 'currency': 'POINT'}, # 指数ポイント x $1000
    # 株価指数
    'S&P 500':   {'unit': 50,     'ticker': '^GSPC', 'currency': 'POINT'}, # E-mini: 指数ポイント x $50
    'NASDAQ 100':{'unit': 20,     'ticker': '^NDX', 'currency': 'POINT'}, # E-mini: 指数ポイント x $20
    'Dow Jones': {'unit': 5,      'ticker': '^DJI', 'currency': 'POINT'}, # E-mini: 指数ポイント x $5
    '日経 225':    {'unit': 500,    'ticker': 'NKD=F', 'currency': 'JPY'},   # CME: 指数ポイント x 500円
    # 商品
    '金 (Gold)':   {'unit': 100,    'ticker': 'GC=F', 'currency': 'USD'}, # 100トロイオンス
    '銀 (Silver)': {'unit': 5000,   'ticker': 'SI=F', 'currency': 'USD'}, # 5000トロイオンス
    '原油 (WTI)':  {'unit': 1000,   'ticker': 'CL=F', 'currency': 'USD'}, # 1000バレル
    '天然ガス':    {'unit': 10000,  'ticker': 'NG=F', 'currency': 'USD'}, # 10,000 MMBtu
    # 債券 (簡略化のため額面価値で代用)
    '米国10年債':  {'unit': 100000, 'ticker': 'ZN=F', 'currency': 'USD_PRICE'},
    '米国30年債':  {'unit': 100000, 'ticker': 'ZB=F', 'currency': 'USD_PRICE'},
}

# --------------------------------------------------------------------------
# --- データ取得と価格取得 (Streamlitのキャッシュ機能を使用) ---
# --------------------------------------------------------------------------

@st.cache_data(ttl=3600) # 1時間キャッシュ
def get_prepared_cot_data():
    """COTデータを取得し、分析用に前処理を行う"""
    df = cot.cot_all(cot_report_type='legacy_fut')
    df['CFTC Contract Market Code'] = df['CFTC Contract Market Code'].astype(str)
    df = df[df['CFTC Contract Market Code'].isin(ASSET_MAP.keys())].copy()
    df['Name'] = df['CFTC Contract Market Code'].map(ASSET_MAP)
    columns_to_keep = [
        'Name', 'As of Date in Form YYYY-MM-DD',
        'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)',
        'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)',
        'Nonreportable Positions-Long (All)', 'Nonreportable Positions-Short (All)'
    ]
    df = df[columns_to_keep]
    df.rename(columns={
        'As of Date in Form YYYY-MM-DD': 'Date',
        'Noncommercial Positions-Long (All)': 'NonComm_Long',
        'Noncommercial Positions-Short (All)': 'NonComm_Short',
        'Commercial Positions-Long (All)': 'Comm_Long',
        'Commercial Positions-Short (All)': 'Comm_Short',
        'Nonreportable Positions-Long (All)': 'Retail_Long',
        'Nonreportable Positions-Short (All)': 'Retail_Short'
    }, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=['Name', 'Date'])
    df['NonComm_Net'] = df['NonComm_Long'] - df['NonComm_Short']
    df['Comm_Net'] = df['Comm_Long'] - df['Comm_Short']
    df['Retail_Net'] = df['Retail_Long'] - df['Retail_Short']
    return df

@st.cache_data(ttl=3600) # 1時間キャッシュ
def get_price(ticker, date_str):
    """指定された日付近の市場価格を取得する (キャッシュキー用に日付を文字列に)"""
    date = pd.to_datetime(date_str)
    try:
        end_date = date + pd.Timedelta(days=4)
        data = yf.download(ticker, start=date, end=end_date, progress=False, auto_adjust=True)
        if data.empty:
            data = yf.download(ticker, start=date - pd.Timedelta(days=7), end=date, progress=False, auto_adjust=True)
        
        if not data.empty:
            price = data['Close'].iloc[-1]
            if hasattr(price, 'item'):
                price = price.item()
            return price
    except Exception:
        pass
    return None

# --------------------------------------------------------------------------
# --- 分析関数 (ロジックは変更なし) ---
# --------------------------------------------------------------------------
def get_cot_index(series, lookback):
    rolling_min = series.rolling(window=lookback).min()
    rolling_max = series.rolling(window=lookback).max()
    return (series - rolling_min) / (rolling_max - rolling_min) * 100

def scan_divergence(df):
    results = []
    today = pd.Timestamp.now()
    for name, group in df.groupby('Name'):
        if len(group) < LOOKBACK_WEEKS: continue
        latest_date = group['Date'].iloc[-1]
        days_diff = (today - latest_date).days
        warning_flag = " (データ古い!)" if days_diff > DATA_FRESHNESS_THRESHOLD_DAYS else ""
        comm_index = get_cot_index(group['Comm_Net'], LOOKBACK_WEEKS).iloc[-1]
        noncomm_index = get_cot_index(group['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1]
        score = noncomm_index - comm_index
        results.append({'銘柄': f"{name}{warning_flag}", '最新データ日': latest_date.strftime('%Y-%m-%d'), 'スコア': score, '投機筋指数': noncomm_index, '実需筋指数': comm_index})
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        column_order = ['銘柄', '最新データ日', 'スコア', '投機筋指数', '実需筋指数']
        df_results = df_results.sort_values(by='スコア', key=abs, ascending=False).reset_index(drop=True)[column_order]
    return df_results

def scan_flow(df):
    results = []
    today = pd.Timestamp.now()
    for name, group in df.groupby('Name'):
        if len(group) < LOOKBACK_WEEKS: continue
        latest_date = group['Date'].iloc[-1]
        days_diff = (today - latest_date).days
        warning_flag = " (データ古い!)" if days_diff > DATA_FRESHNESS_THRESHOLD_DAYS else ""
        net_change = group['NonComm_Net'].diff()
        latest_change = net_change.iloc[-1]
        change_mean = net_change.rolling(window=LOOKBACK_WEEKS).mean().iloc[-1]
        change_std = net_change.rolling(window=LOOKBACK_WEEKS).std().iloc[-1]
        z_score = (latest_change - change_mean) / change_std if change_std != 0 else 0
        results.append({'銘柄': f"{name}{warning_flag}", '最新データ日': latest_date.strftime('%Y-%m-%d'), 'Zスコア': z_score, '週次変化': latest_change})
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        column_order = ['銘柄', '最新データ日', 'Zスコア', '週次変化']
        df_results = df_results.sort_values(by='Zスコア', key=abs, ascending=False).reset_index(drop=True)[column_order]
    return df_results

def scan_reversal(df):
    results = []
    today = pd.Timestamp.now()
    for name, group in df.groupby('Name'):
        if len(group) < LOOKBACK_WEEKS: continue
        latest_date = group['Date'].iloc[-1]
        days_diff = (today - latest_date).days
        warning_flag = " (データ古い!)" if days_diff > DATA_FRESHNESS_THRESHOLD_DAYS else ""
        noncomm_index = get_cot_index(group['NonComm_Net'], LOOKBACK_WEEKS).iloc[-1]
        retail_index = get_cot_index(group['Retail_Net'], LOOKBACK_WEEKS).iloc[-1]
        score = noncomm_index - retail_index
        results.append({'銘柄': f"{name}{warning_flag}", '最新データ日': latest_date.strftime('%Y-%m-%d'), 'スコア': score, '機関投資家指数': noncomm_index, '個人投資家指数': retail_index})
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        column_order = ['銘柄', '最新データ日', 'スコア', '機関投資家指数', '個人投資家指数']
        df_results = df_results.sort_values(by='スコア', key=abs, ascending=False).reset_index(drop=True)[column_order]
    return df_results

def scan_monetary_flow(df):
    results = []
    price_info_results = []
    usdjpy_rate = get_price('JPY=X', (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y-%m-%d'))
    
    for name, group in df.groupby('Name'):
        if len(group) < 2 or name not in CONTRACT_SPECS:
            continue
            
        spec = CONTRACT_SPECS[name]
        latest = group.iloc[-1]
        previous = group.iloc[-2]

        price = get_price(spec['ticker'], latest['Date'].strftime('%Y-%m-%d'))
        if price is None:
            continue

        contract_value_usd = 0
        if spec['currency'] in ['USD', 'POINT', 'USD_PRICE']:
            contract_value_usd = spec['unit'] * price
        elif spec['currency'] == 'JPY_PER_USD':
            if price != 0:
                contract_value_usd = spec['unit'] / price
        elif spec['currency'] == 'JPY':
            if usdjpy_rate and usdjpy_rate != 0:
                contract_value_usd = (spec['unit'] * price) / usdjpy_rate
        
        if contract_value_usd == 0:
            continue

        price_info_results.append({
            '銘柄': name,
            'ティッカー': spec['ticker'],
            '価格取得日': latest['Date'].strftime('%Y-%m-%d'),
            '取得価格': price,
            '通貨': spec['currency'],
            '1契約のドル価値': contract_value_usd
        })

        noncomm_net_chg = latest['NonComm_Net'] - previous['NonComm_Net']
        comm_net_chg = latest['Comm_Net'] - previous['Comm_Net']
        
        noncomm_flow_usd = noncomm_net_chg * contract_value_usd
        comm_flow_usd = comm_net_chg * contract_value_usd
        
        results.append({
            '銘柄': name,
            '投機筋フロー(USD)': noncomm_flow_usd,
            '実需筋フロー(USD)': comm_flow_usd,
        })
        
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        df_results['ソートキー'] = df_results['投機筋フロー(USD)'].abs()
        df_results = df_results.sort_values(by='ソートキー', ascending=False).drop(columns='ソートキー').reset_index(drop=True)
    
    return df_results, pd.DataFrame(price_info_results)

# --------------------------------------------------------------------------
# --- Streamlit UI 表示 ---
# --------------------------------------------------------------------------

st.title("COTレポート分析スキャナー")

# --- 説明文 ---
with st.expander("分析ロジックと結果の見方"):
    st.markdown(f"""
    このスキャナーは、最新のCOTレポートを「枚数ベース」と「金額ベース」で分析します。
    銘柄名の隣に「(データ古い!)」と表示されている場合、そのデータは
    **{DATA_FRESHNESS_THRESHOLD_DAYS}日以上前**のものですのでご注意ください。

    ---
    #### 各テーブルの列（カラム）が示す数値の範囲

    **[手法1 & 3: ダイバージェンス & 転換点スキャナー]**
    - **スコア**: `-100` (極端な弱気) から `+100` (極端な強気) の範囲で変動します。
    - **各指数**: `0` (過去{LOOKBACK_WEEKS}週で最弱) から `100` (過去{LOOKBACK_WEEKS}週で最強) の範囲で変動します。

    **[手法2: 大口資金フロー・スキャナー]**
    - **Zスコア**: 理論上の範囲は無制限ですが、通常は`-3.0`～`+3.0`の範囲に収まります。絶対値が`2.0`を超えると、統計的に稀なポジション変化と解釈できます。
    - **週次変化**: ポジションの増減枚数であり、理論上の範囲は無制限です。

    **[手法4: 金額ベース資金フロー・スキャナー]**
    - **フロー(USD)**: ポジションの週次変化をドル換算した金額です。市場間で資金の動きを比較するのに役立ちます。
    """)

# --- データ取得 ---
with st.spinner('最新のCOTレポートデータを取得・処理しています...'):
    all_data = get_prepared_cot_data()

st.success('データの準備が完了しました。')

# --- 分析結果の表示 ---
st.header("手法1: ダイバージェンス・スキャナー (投機筋 vs 実需筋)")
divergence_top = scan_divergence(all_data)
st.dataframe(divergence_top.style.format({
    'スコア': '{:.1f}',
    '投機筋指数': '{:.1f}',
    '実需筋指数': '{:.1f}'
}), use_container_width=True)

st.header("手法2: 大口資金フロー・スキャナー (投機筋ポジションの週次変化)")
flow_top = scan_flow(all_data)
st.dataframe(flow_top.style.format({
    'Zスコア': '{:.2f}',
    '週次変化': '{:,.0f}'
}), use_container_width=True)

st.header("手法3: 転換点スキャナー (機関投資家 vs 個人投資家)")
reversal_top = scan_reversal(all_data)
st.dataframe(reversal_top.style.format({
    'スコア': '{:.1f}',
    '機関投資家指数': '{:.1f}',
    '個人投資家指数': '{:.1f}'
}), use_container_width=True)

st.header("手法4: 金額ベース資金フロー・スキャナー (週次変化のドル換算)")
with st.spinner('市場価格を取得し、金額ベースのフローを計算しています...'):
    monetary_flow_top, price_info_df = scan_monetary_flow(all_data)
st.dataframe(monetary_flow_top.style.format({
    '投機筋フロー(USD)': '${:,.0f}',
    '実需筋フロー(USD)': '${:,.0f}'
}), use_container_width=True)


# --- 詳細データ表示 ---
st.header("各銘柄の最新COTデータ詳細 (カッコ内は前週比)")
today = pd.Timestamp.now()
for market_code, display_name in ASSET_MAP.items():
    asset_data = all_data[all_data['Name'] == display_name]
    if len(asset_data) < 2:
        st.subheader(f"--- {display_name} ---")
        st.warning("比較対象となる前週のデータが不足しています。")
        continue

    st.subheader(f"--- {display_name} ---")
    
    latest = asset_data.iloc[-1]
    previous = asset_data.iloc[-2]
    
    latest_date = latest['Date']
    days_diff = (today - latest_date).days
    st.caption(f"データ日付: {latest['Date'].strftime('%Y-%m-%d')}")
    if days_diff > DATA_FRESHNESS_THRESHOLD_DAYS:
        st.warning(f"!!! 警告: このデータは{days_diff}日前のもので古くなっています !!!")

    # データフレームを作成
    def format_change(current, prev):
        change = current - prev
        return f"{current:,.0f} ({change:+,d})"

    def format_pct_change(current_long, current_short, prev_long, prev_short):
        current_total = current_long + current_short
        prev_total = prev_long + prev_short
        
        current_pct = (current_long / current_total) * 100 if current_total > 0 else 0
        prev_pct = (prev_long / prev_total) * 100 if prev_total > 0 else 0
        
        pct_change = current_pct - prev_pct
        return f"{current_pct:.1f}% ({pct_change:+.1f}%)"

    table_data = {
        "Long (chg)": [
            format_change(latest['Comm_Long'], previous['Comm_Long']),
            format_change(latest['NonComm_Long'], previous['NonComm_Long']),
            format_change(latest['Retail_Long'], previous['Retail_Long'])
        ],
        "Short (chg)": [
            format_change(latest['Comm_Short'], previous['Comm_Short']),
            format_change(latest['NonComm_Short'], previous['NonComm_Short']),
            format_change(latest['Retail_Short'], previous['Retail_Short'])
        ],
        "Net (chg)": [
            format_change(latest['Comm_Net'], previous['Comm_Net']),
            format_change(latest['NonComm_Net'], previous['NonComm_Net']),
            format_change(latest['Retail_Net'], previous['Retail_Net'])
        ],
        "Long % (chg)": [
            format_pct_change(latest['Comm_Long'], latest['Comm_Short'], previous['Comm_Long'], previous['Comm_Short']),
            format_pct_change(latest['NonComm_Long'], latest['NonComm_Short'], previous['NonComm_Long'], previous['NonComm_Short']),
            format_pct_change(latest['Retail_Long'], latest['Retail_Short'], previous['Retail_Long'], previous['Retail_Short'])
        ]
    }
    
    df_display = pd.DataFrame(table_data, index=["実需筋", "大口投機筋", "小口投機筋"])
    st.dataframe(df_display, use_container_width=True)

# --- 検証用データ ---
with st.expander("[検証用] 金額換算に使用した価格情報"):
    st.dataframe(price_info_df.style.format({
        '取得価格': '{:.4f}',
        '1契約のドル価値': '${:,.0f}'
    }), use_container_width=True)


