"""K线图可视化展示页面"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import SUPPORTED_FREQS
from src.common.data.data_manager import DataManager

# 页面配置
st.set_page_config(
    page_title="K线图展示",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 K线图查看")
st.markdown("---")

# 快捷跳转栏
st.subheader("⚡ 快捷跳转")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📥 数据管理", use_container_width=True):
        st.switch_page("pages/1_📥_数据管理.py")
with col2:
    if st.button("🔍 形态选股", use_container_width=True):
        st.switch_page("pages/2_🔍_形态相似性选股.py")
with col3:
    if st.button("⚙️ 系统配置", use_container_width=True):
        st.switch_page("pages/4_⚙️_系统配置.py")

st.markdown("---")

# 初始化数据管理器
@st.cache_resource
def init_data_manager():
    return DataManager()

dm = init_data_manager()

# 获取股票列表
stock_df = dm.get_stock_list()
stock_options = [f"{row.ts_code} - {row.name}" for _, row in stock_df.iterrows()]
stock_dict = {f"{row.ts_code} - {row.name}": row.ts_code for _, row in stock_df.iterrows()}

# ========== 顶部控制栏 ==========
col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    selected_stock_label = st.selectbox(
        "🔍 选择股票",
        options=[""] + stock_options,
        format_func=lambda x: x if x else "请搜索选择股票...",
    )

with col2:
    freq_options = list(SUPPORTED_FREQS.items())
    selected_freq_label = st.selectbox(
        "📅 时间周期",
        options=[name for _, name in freq_options],
        index=0,
    )
    # 根据选择的名称反查code
    selected_freq = [k for k, v in freq_options if v == selected_freq_label][0]

with col3:
    show_ma = st.checkbox("📊 显示均线", value=True)

# 均线设置
ma_periods = []
if show_ma:
    ma_col1, ma_col2, ma_col3, ma_col4 = st.columns(4)
    with ma_col1:
        if st.checkbox("MA5", value=True):
            ma_periods.append(5)
    with ma_col2:
        if st.checkbox("MA10", value=True):
            ma_periods.append(10)
    with ma_col3:
        if st.checkbox("MA20", value=True):
            ma_periods.append(20)
    with ma_col4:
        if st.checkbox("MA60", value=False):
            ma_periods.append(60)

st.markdown("---")

# ========== 加载并展示K线 ==========
if selected_stock_label:
    target_ts_code = stock_dict[selected_stock_label]

    # 检查数据是否存在
    if not dm.is_data_available(target_ts_code, selected_freq):
        st.warning(f"⚠️ {selected_stock_label} 的 {selected_freq_label} 数据尚未同步，请先到「数据管理」页面同步数据")
    else:
        # 获取数据
        df_full = dm.get_bars(target_ts_code, selected_freq)
        total_len = len(df_full)

        if total_len < 5:
            st.error("数据太少，无法展示K线")
        else:
            st.success(f"✅ 已加载 {total_len} 根K线数据")

            # 日期范围选择
            if 'trade_date' in df_full.columns:
                df_full['trade_date_str'] = df_full['trade_date'].astype(str)

                # 转换日期格式用于显示
                df_full['date_display'] = pd.to_datetime(df_full['trade_date'], format='%Y%m%d')

                # 最近交易日信息
                latest = df_full.iloc[-1]
                col_a, col_b, col_c, col_d, col_e = st.columns(5)
                with col_a:
                    st.metric("📅 最新日期", latest['date_display'].strftime('%Y-%m-%d'))
                with col_b:
                    st.metric("📈 收盘", f"{latest['close']:.2f}")
                with col_c:
                    st.metric("🔺 最高", f"{latest['high']:.2f}")
                with col_d:
                    st.metric("🔻 最低", f"{latest['low']:.2f}")
                with col_e:
                    st.metric("📊 成交量", f"{latest['volume']:,.0f}")

            st.markdown("---")

            # 显示范围选择
            st.subheader("📊 选择显示区间")

            range_mode = st.radio("范围选择方式", ["显示全部", "显示最近N根", "手动选择区间"], horizontal=True)

            if range_mode == "显示全部":
                start_idx, end_idx = 0, total_len
            elif range_mode == "显示最近N根":
                n_bars = st.slider("显示最近N根K线", min_value=20, max_value=total_len, value=min(120, total_len))
                start_idx, end_idx = max(0, total_len - n_bars), total_len
            else:
                # 手动选择
                start_idx = st.slider("起始位置", min_value=0, max_value=total_len-5, value=max(0, total_len-120))
                end_idx = st.slider("结束位置", min_value=start_idx+3, max_value=total_len, value=total_len)

            df = df_full.iloc[start_idx:end_idx].copy()
            actual_len = len(df)

            st.info(f"📈 正在显示 {actual_len} 根K线")

            # ========== 计算技术指标 ==========
            # MA均线
            if show_ma:
                for period in ma_periods:
                    df[f'MA{period}'] = df['close'].rolling(window=period).mean()

            # 涨跌颜色
            df['color'] = df.apply(
                lambda row: 'red' if row['close'] >= row['open'] else 'green',
                axis=1
            )

            # ========== 绘制K线图 ==========
            # 准备X轴
            if 'date_display' in df.columns:
                x_data = df['date_display']
            else:
                x_data = list(range(actual_len))

            # 创建子图：K线 + 成交量
            fig = make_subplots(
                rows=2, cols=1,
                row_heights=[3, 1],
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=(f"{selected_stock_label} - {selected_freq_label} K线图", "成交量"),
            )

            # 蜡烛图
            fig.add_trace(go.Candlestick(
                x=x_data,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                increasing_line_color='red',
                decreasing_line_color='green',
                increasing_fillcolor='rgba(255,0,0,0.7)',
                decreasing_fillcolor='rgba(0,255,0,0.7)',
                name='K线',
                hovertext=[
                    f"日期: {d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else d}<br>"
                    f"开盘: {o:.2f}<br>"
                    f"最高: {h:.2f}<br>"
                    f"最低: {l:.2f}<br>"
                    f"收盘: {c:.2f}<br>"
                    f"成交量: {v:,.0f}"
                    for d, o, h, l, c, v in zip(x_data, df['open'], df['high'], df['low'], df['close'], df['volume'])
                ],
                hoverinfo="text",
            ), row=1, col=1)

            # 添加均线
            ma_colors = {
                5: '#FFD700',   # 金色
                10: '#9370DB',  # 紫色
                20: '#1E90FF',  # 蓝色
                60: '#FF6347',  # 橙色
            }

            if show_ma:
                for period in ma_periods:
                    if f'MA{period}' in df.columns:
                        color = ma_colors.get(period, '#808080')
                        fig.add_trace(go.Scatter(
                            x=x_data,
                            y=df[f'MA{period}'],
                            mode='lines',
                            line=dict(color=color, width=1.5),
                            name=f'MA{period}',
                            hovertemplate=f'MA{period}:'+ '%{y:.2f}<extra></extra>',
                        ), row=1, col=1)

            # 成交量柱状图
            fig.add_trace(go.Bar(
                x=x_data,
                y=df['volume'],
                marker_color=df['color'],
                name='成交量',
                opacity=0.7,
                hovertemplate='成交量: %{y:,.0f}<extra></extra>',
            ), row=2, col=1)

            # 图表布局设置
            fig.update_layout(
                height=700,
                margin=dict(l=10, r=10, t=50, b=10),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
                hovermode='x unified',
                dragmode='pan',
            )

            # 去掉X轴范围滑块
            fig.update_layout(xaxis_rangeslider_visible=False)

            # Y轴标签
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=2, col=1)

            # 显示图表
            st.plotly_chart(fig, use_container_width=True)

            # ========== 数据预览表格 ==========
            st.markdown("---")
            with st.expander("📋 查看原始数据"):
                display_cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
                display_cols = [c for c in display_cols if c in df.columns]
                display_df = df[display_cols].copy()

                # 格式化数字
                for col in ['open', 'high', 'low', 'close']:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].round(2)
                if 'volume' in display_df.columns:
                    display_df['volume'] = display_df['volume'].astype(int)

                st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    # 还没选股票时的引导
    st.info("👈 请从上方下拉框选择一只股票开始查看K线图")

    st.markdown("---")
    st.subheader("💡 功能说明")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.success("""
        **📈 专业蜡烛图**

        - 红涨绿跌标准配色
        - 鼠标悬停显示详细数据
        - 支持缩放、平移、框选
        """)

    with col2:
        st.success("""
        **📊 MA均线系统**

        - MA5/MA10/MA20/MA60可选
        - 实时计算，立即显示
        - 不同颜色区分周期
        """)

    with col3:
        st.success("""
        **📅 多周期切换**

        - 支持日/周/月/季/年线
        - 自动从日线合成
        - 一键切换，无缝衔接
        """)

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
