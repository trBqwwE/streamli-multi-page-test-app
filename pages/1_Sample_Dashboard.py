import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="サンプルダッシュボード", page_icon="📈")

st.title("📈 サンプルダッシュボード")
st.write("このページは、`pages`フォルダの中にあるPythonスクリプトです。")

st.markdown("---")

# インタラクティブなウィジェットの例
st.subheader("データ生成オプション")
num_points = st.slider("データポイントの数", 5, 100, 50)
chart_color = st.color_picker("グラフの色", "#00A9FF")


# サンプルデータの生成
data = pd.DataFrame({
    '日付': pd.to_datetime(pd.date_range('2025-01-01', periods=num_points, freq='D')),
    '値': np.random.randn(num_points).cumsum()
}).set_index('日付')

st.subheader("生成されたデータ")
st.dataframe(data.tail())

st.subheader("折れ線グラフ")
st.line_chart(data, color=chart_color)