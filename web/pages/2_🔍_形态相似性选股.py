"""形态相似性选股页面"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import SUPPORTED_FREQS
from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.pattern_service import PatternMatchingService


# 页面配置
st.set_page_config(
    page_title="形态相似性选股",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化服务
@st.cache_resource
def init_services():
    dm = DataManager()
    pattern_service = PatternMatchingService(dm)
    return dm, pattern_service


dm, pattern_service = init_services()

# 标题
st.title("🔍 形态相似性选股")
st.markdown("---")

# 快捷跳转栏
st.subheader("⚡ 快捷跳转")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📥 数据管理", use_container_width=True):
        st.switch_page("pages/1_📥_数据管理.py")
with col2:
    if st.button("📈 查看K线图", use_container_width=True):
        st.switch_page("pages/3_📈_K线图展示.py")
with col3:
    if st.button("⚙️ 系统配置", use_container_width=True):
        st.switch_page("pages/4_⚙️_系统配置.py")

st.markdown("---")

# 获取股票列表
stock_df = dm.get_stock_list()
stock_options = [f"{row.ts_code} - {row.name}" for _, row in stock_df.iterrows()]
stock_dict = {f"{row.ts_code} - {row.name}": row.ts_code for _, row in stock_df.iterrows()}

# 目标股票选择
selected_stock_label = st.selectbox(
    "选择目标股票",
    options=[""] + stock_options,
    format_func=lambda x: x if x else "请搜索选择股票...",
)

# 时间周期选择
freq_options = list(SUPPORTED_FREQS.items())
freq_label = st.selectbox(
    "选择时间周期",
    options=[f"{name} ({code})" for code, name in freq_options],
    index=freq_options.index(('D', '日线')) if ('D', '日线') in freq_options else 0,
)
selected_freq = [k for k, v in freq_options if f"{v} ({k})" == freq_label][0]

# 参数设置
with st.expander("⚙️ 高级参数设置", expanded=False):
    top_k = st.slider("返回Top N结果", min_value=5, max_value=50, value=20, step=5)
    use_mp = st.checkbox("使用多进程加速", value=True)
    st.caption("多进程可以加快计算速度，但需要更多内存")

st.markdown("---")

if selected_stock_label:
    target_ts_code = stock_dict[selected_stock_label]

    # 检查数据是否存在
    if not dm.is_data_available(target_ts_code, selected_freq):
        st.warning(f"⚠️ {selected_stock_label} 的 {selected_freq} 数据尚未同步，请先到「数据管理」页面同步数据")
    else:
        # 获取数据显示区间选择
        df_full = dm.get_bars(target_ts_code, selected_freq)
        total_len = len(df_full)

        if total_len < 5:
            st.error("数据长度太短，无法匹配")
        else:
            st.info(f"✅ 数据已加载，共 {total_len} 根K线")

            # 让用户选择区间
            st.subheader("选择目标形态区间")

            if 'trade_date' in df_full.columns:
                dates = df_full['trade_date'].astype(str).tolist()
                start_idx = st.slider(
                    "起始位置",
                    min_value=0,
                    max_value=max(0, total_len - 5),
                    value=max(0, total_len - 60),
                )
                end_idx = st.slider(
                    "结束位置",
                    min_value=start_idx + 3,
                    max_value=total_len,
                    value=total_len,
                )
                selected_df = df_full.iloc[start_idx:end_idx]
                st.write(f"已选择区间: {dates[start_idx]} ~ {dates[end_idx-1]}，长度 {end_idx - start_idx} 根K线")
            else:
                start_idx = st.slider(
                    "起始位置",
                    min_value=0,
                    max_value=max(0, total_len - 5),
                    value=max(0, total_len - 60),
                )
                end_idx = st.slider(
                    "结束位置",
                    min_value=start_idx + 3,
                    max_value=total_len,
                    value=total_len,
                )
                selected_df = df_full.iloc[start_idx:end_idx]
                st.write(f"已选择区间: 长度 {end_idx - start_idx} 根K线")

            # 绘制目标形态
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(selected_df))),
                y=selected_df['close'].values,
                mode='lines+markers',
                name='收盘价',
                line=dict(width=2, color='blue'),
            ))
            fig.update_layout(
                title=f"目标形态: {selected_stock_label}",
                xaxis_title="K线序号",
                yaxis_title="价格",
                height=300,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # 开始匹配按钮
            if st.button("🚀 开始匹配", type="primary", use_container_width=True):
                with st.spinner("正在匹配中，请稍候..."):
                    results, _ = pattern_service.match(
                        target_ts_code,
                        selected_freq,
                        start_idx=start_idx,
                        end_idx=end_idx,
                        top_k=top_k,
                        use_multiprocessing=use_mp,
                        verbose=False,
                    )

                if results is None or len(results) == 0:
                    st.error("没有找到匹配结果，请确认数据已同步")
                else:
                    st.success(f"匹配完成，找到 {len(results)} 个相似形态")
                    st.subheader("📋 匹配结果")

                    # 显示结果表格
                    result_df = pd.DataFrame([
                        {
                            "排名": i + 1,
                            "股票代码": r['ts_code'],
                            "名称": r['name'],
                            "相似度": f"{r['score']:.3f}",
                            "起始位置": r['start_idx'],
                        }
                        for i, r in enumerate(results)
                    ])
                    st.dataframe(result_df, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.subheader("📊 对比图表")

                    # 获取目标数据用于对比
                    target_prices = selected_df['close'].values
                    target_len = len(target_prices)

                    # 每个结果显示对比图
                    for i, result in enumerate(results[:10]):
                        with st.expander(f"#{i+1} {result['ts_code']} {result['name']} (相似度: {result['score']:.3f})", expanded=i < 3):
                            # 获取匹配数据
                            match_df = pattern_service.get_match_result_with_data(
                                result, selected_freq, target_len
                            )

                            if match_df is None or len(match_df) == 0:
                                st.error("无法加载匹配数据")
                                continue

                            # 创建对比图
                            fig = make_subplots(
                                rows=2, cols=1,
                                subplot_titles=("目标形态", f"匹配结果: {result['ts_code']} {result['name']}"),
                                shared_xaxes=True,
                                vertical_spacing=0.15,
                            )

                            # 目标
                            norm_target = (target_prices - target_prices.min()) / (target_prices.max() - target_prices.min() + 1e-8)
                            fig.add_trace(
                                go.Scatter(
                                    x=list(range(len(target_prices))),
                                    y=norm_target,
                                    mode='lines+markers',
                                    line=dict(color='blue', width=2),
                                    name='目标',
                                ),
                                row=1, col=1,
                            )

                            # 匹配结果
                            match_prices = match_df['close'].values
                            norm_match = (match_prices - match_prices.min()) / (match_prices.max() - match_prices.min() + 1e-8)
                            fig.add_trace(
                                go.Scatter(
                                    x=list(range(len(match_prices))),
                                    y=norm_match,
                                    mode='lines+markers',
                                    line=dict(color='red', width=2),
                                    name='匹配',
                                ),
                                row=2, col=1,
                            )

                            fig.update_layout(
                                height=400,
                                margin=dict(l=0, r=0, t=40, b=0),
                                showlegend=True,
                            )
                            fig.update_yaxes(title_text="归一化价格", range=[-0.05, 1.05])

                            st.plotly_chart(fig, use_container_width=True)

                            # 如果有日期信息，显示日期范围
                            if 'trade_date' in match_df.columns:
                                start_date = str(match_df['trade_date'].iloc[0])
                                end_date = str(match_df['trade_date'].iloc[-1])
                                st.caption(f"匹配区间日期: {start_date} ~ {end_date}")

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
