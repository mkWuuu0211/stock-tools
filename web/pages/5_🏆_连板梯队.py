"""连板梯队页面 - 涨停股票分组和相似度分析"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.limit_up_service import LimitUpService
from src.pattern_matcher.algorithm.detector import LimitUpDetector
from config.settings import MAX_STOCKS_PER_TIER, CONSECUTIVE_DAYS_TO_SHOW

# 页面配置
st.set_page_config(
    page_title="连板梯队 - 股票工具集合",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏆 连板梯队")
st.markdown("---")

# 初始化服务
@st.cache_resource
def init_services():
    dm = DataManager()
    limit_service = LimitUpService(dm)
    detector = LimitUpDetector()
    return dm, limit_service, detector

dm, limit_service, detector = init_services()

# 获取股票列表（用于显示股票名称）
stock_list = dm.get_stock_list()
stock_name_map = dict(zip(stock_list['ts_code'], stock_list['name']))
stock_industry_map = dict(zip(stock_list['ts_code'], stock_list.get('industry', pd.Series(['未知'] * len(stock_list)))))


# ========== 智能日期选择 ==========
@st.cache_data(ttl=3600)
def find_latest_available_date():
    """智能检测最新有数据的日期"""
    all_stocks = dm.get_all_local_stocks('D')
    date_coverage = {}

    # 检查最近30个交易日
    today = datetime.now()
    for days_ago in range(30):
        check_date = today - timedelta(days=days_ago)
        if check_date.weekday() >= 5:  # 跳过周末
            continue
        date_str = check_date.strftime('%Y%m%d')
        date_coverage[date_str] = 0

    # 抽样检查覆盖率（检查前100只股票）
    sample_stocks = all_stocks[:100]
    for ts_code in sample_stocks:
        df = dm.get_bars(ts_code, 'D')
        if df is not None and not df.empty:
            last_date = str(df.iloc[-1]['trade_date'])
            if last_date in date_coverage:
                date_coverage[last_date] += 1

    # 找到覆盖率最高的最近日期
    sorted_dates = sorted(date_coverage.keys(), reverse=True)
    for date_str in sorted_dates:
        if date_coverage[date_str] >= 50:  # 至少50%的股票有数据
            return date_str, date_coverage[date_str], len(sample_stocks)

    # 如果都不满足，返回覆盖率最高的
    if sorted_dates:
        best_date = max(sorted_dates, key=lambda d: date_coverage[d])
        return best_date, date_coverage[best_date], len(sample_stocks)

    return None, 0, 0

# 查找最新可用日期
latest_date, coverage_count, total_sampled = find_latest_available_date()

if latest_date:
    default_date = datetime.strptime(latest_date, '%Y%m%d')
else:
    default_date = datetime.now() - timedelta(days=1)

# 日期选择器
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_date = st.date_input(
        "选择日期",
        value=default_date,
        help="选择要查看的日期（需要该日有日线数据）"
    )

with col2:
    # 显示数据覆盖率
    date_str = selected_date.strftime('%Y%m%d')
    if latest_date and date_str == latest_date:
        coverage_pct = coverage_count / total_sampled * 100
        st.success(f"✅ 推荐日期 | 数据覆盖率: {coverage_pct:.0f}% ({coverage_count}/{total_sampled})")
    else:
        st.info(f"💡 推荐日期: {latest_date}" if latest_date else "⚠️ 未找到可用数据")

with col3:
    st.write("")  # 占位
    st.write("")  # 占位
    if st.button("🔄 刷新扫描", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 转换日期格式
date_str = selected_date.strftime('%Y%m%d')


# ========== 扫描涨停股票 ==========
st.subheader(f"📊 {date_str} 涨停扫描")

with st.spinner("正在扫描涨停股票..."):
    try:
        scan_result = limit_service.scan_limit_up_on_date(date_str, use_cache=True)
        limit_up_stocks = scan_result['stocks']
        total_scanned = scan_result['total_scanned']

        st.success(f"✅ 扫描完成：共 {total_scanned} 只股票，发现 {len(limit_up_stocks)} 只涨停")

    except Exception as e:
        st.error(f"扫描失败：{str(e)}")
        st.info("请确保已同步日线数据，且选择的日期在数据范围内")
        st.stop()


# ========== 按连板天数分组 ==========
tiers = limit_service.get_limit_up_tiers(date_str)

tier_names = {
    '1': '首板',
    '2': '2连板',
    '3': '3连板',
    '4+': '4连板+'
}

# 显示统计
cols = st.columns(4)
for idx, (tier_key, tier_stocks) in enumerate(tiers.items()):
    with cols[idx]:
        st.metric(
            label=tier_names[tier_key],
            value=f"{len(tier_stocks)} 只",
            delta="涨停" if tier_stocks else None
        )

st.markdown("---")


# ========== 筛选和排序 ==========
st.subheader("🔧 筛选和排序")

col1, col2, col3 = st.columns(3)

with col1:
    # 板块筛选
    board_filter = st.multiselect(
        "板块筛选",
        options=['主板', '创业板', '科创板', '北交所', 'ST'],
        default=['主板', '创业板', '科创板', '北交所'],
        help="选择要显示的板块"
    )

with col2:
    # 排序方式
    sort_by = st.selectbox(
        "排序方式",
        options=['连板天数', '涨幅', '成交量', '成交额'],
        index=0
    )

with col3:
    # 行业筛选（可选）
    all_industries = sorted(set(stock_industry_map.values()))
    industry_filter = st.multiselect(
        "行业筛选",
        options=all_industries,
        default=[],
        help="留空表示不按行业筛选"
    )

# 应用筛选
def apply_filters(tier_stocks):
    """应用筛选条件"""
    filtered = []
    for ts_code, df, result in tier_stocks:
        # 板块筛选
        board_type = detector.get_board_type(ts_code)
        board_name_map = {
            'main': '主板',
            'chinext': '创业板',
            'star': '科创板',
            'bse': '北交所',
            'st': 'ST'
        }
        if board_name_map.get(board_type, '') not in board_filter:
            continue

        # 行业筛选
        if industry_filter:
            industry = stock_industry_map.get(ts_code, '未知')
            if industry not in industry_filter:
                continue

        filtered.append((ts_code, df, result))

    # 排序
    if sort_by == '涨幅':
        filtered.sort(key=lambda x: (x[1].iloc[-1]['close'] - x[1].iloc[-2]['close']) / x[1].iloc[-2]['close'], reverse=True)
    elif sort_by == '成交量':
        filtered.sort(key=lambda x: x[1].iloc[-1].get('volume', x[1].iloc[-1].get('vol', 0)), reverse=True)
    elif sort_by == '成交额':
        filtered.sort(key=lambda x: x[1].iloc[-1].get('amount', 0), reverse=True)
    # 连板天数已经在分组时排好

    return filtered

st.markdown("---")


# ========== 显示连板梯队 ==========
def plot_enhanced_kline(df: pd.DataFrame, ts_code: str, days: int = 20):
    """增强版迷你K线图 - 蜡烛图 + 成交量"""
    recent_df = df.tail(days)

    # 创建子图：K线 + 成交量
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[3, 1],
        shared_xaxes=True,
        vertical_spacing=0.05
    )

    # K线蜡烛图
    fig.add_trace(go.Candlestick(
        x=list(range(len(recent_df))),
        open=recent_df['open'].values,
        high=recent_df['high'].values,
        low=recent_df['low'].values,
        close=recent_df['close'].values,
        increasing_line_color='red',
        decreasing_line_color='green',
        increasing_fillcolor='red',
        decreasing_fillcolor='green',
        name='K线',
        showlegend=False
    ), row=1, col=1)

    # 标记涨停日（用金色星星）
    limit_up_days = []
    for i in range(1, len(recent_df)):
        prev_close = recent_df.iloc[i-1]['close']
        curr_close = recent_df.iloc[i]['close']
        pct_change = (curr_close - prev_close) / prev_close

        threshold = detector.get_threshold(ts_code)
        if pct_change >= threshold * (1 - detector.tolerance):
            limit_up_days.append((i, curr_close))

    if limit_up_days:
        fig.add_trace(go.Scatter(
            x=[d[0] for d in limit_up_days],
            y=[d[1] for d in limit_up_days],
            mode='markers',
            marker=dict(symbol='star', size=14, color='gold', line=dict(width=2, color='orange')),
            name='涨停',
            showlegend=False
        ), row=1, col=1)

    # 成交量柱状图
    vol_col = 'volume' if 'volume' in recent_df.columns else 'vol'
    if vol_col in recent_df.columns:
        colors = ['red' if recent_df.iloc[i]['close'] >= recent_df.iloc[i]['open'] else 'green'
                  for i in range(len(recent_df))]
        fig.add_trace(go.Bar(
            x=list(range(len(recent_df))),
            y=recent_df[vol_col].values,
            marker_color=colors,
            name='成交量',
            showlegend=False
        ), row=2, col=1)

    fig.update_layout(
        height=180,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        xaxis2=dict(visible=False),
        yaxis2=dict(visible=False)
    )

    return fig


# 显示每个梯队
for tier_key, tier_stocks in tiers.items():
    if not tier_stocks:
        continue

    # 应用筛选
    filtered_stocks = apply_filters(tier_stocks)

    if not filtered_stocks:
        continue

    tier_name = tier_names[tier_key]
    st.subheader(f"🔥 {tier_name} ({len(filtered_stocks)} 只)")

    # 计算分组内相似度
    similarity_map = limit_service.calculate_similarity_in_group(filtered_stocks, top_k=3)

    # 限制显示数量
    display_stocks = filtered_stocks[:MAX_STOCKS_PER_TIER]

    # 网格显示
    cols_per_row = 3
    for row_idx in range(0, len(display_stocks), cols_per_row):
        row_cols = st.columns(cols_per_row)

        for col_idx, col in enumerate(row_cols):
            stock_idx = row_idx + col_idx
            if stock_idx >= len(display_stocks):
                break

            ts_code, df, result = display_stocks[stock_idx]
            stock_name = stock_name_map.get(ts_code, ts_code)
            consecutive_days = result['consecutive_days']
            industry = stock_industry_map.get(ts_code, '未知')

            with col:
                # 标题：股票名称 + 代码 + 行业
                st.markdown(f"**{stock_name}** ({ts_code})")
                st.caption(f"🏭 {industry} | 连板: {consecutive_days}天")

                # 获取最新价格信息
                latest = df.iloc[-1]
                prev_close = df.iloc[-2]['close'] if len(df) >= 2 else latest['close']
                pct_change = (latest['close'] - prev_close) / prev_close * 100

                # 价格和成交量信息
                vol_col = 'volume' if 'volume' in df.columns else 'vol'
                vol = latest.get(vol_col, 0)
                amount = latest.get('amount', 0)

                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric(
                        label="收盘价",
                        value=f"¥{latest['close']:.2f}",
                        delta=f"{pct_change:.2f}%"
                    )
                with col_b:
                    st.metric(
                        label="成交量",
                        value=f"{vol/10000:.1f}万" if vol > 10000 else f"{vol:.0f}",
                        delta=f"{amount/100000000:.2f}亿" if amount > 100000000 else None
                    )

                # 增强版K线图
                st.plotly_chart(plot_enhanced_kline(df, ts_code), use_container_width=True)

                # 相似股票（用进度条展示相似度）
                if ts_code in similarity_map and similarity_map[ts_code]:
                    similar = similarity_map[ts_code]
                    st.markdown("**相似股票:**")
                    for sim_code, score in similar[:2]:
                        sim_name = stock_name_map.get(sim_code, sim_code)
                        # 用进度条展示相似度
                        score_pct = score * 100
                        color = "🟢" if score >= 0.95 else "🟡" if score >= 0.85 else "🔴"
                        st.caption(f"{color} {sim_name}: {score_pct:.1f}%")
                        st.progress(score)

                # 展开详情
                with st.expander("🔍 查看详情"):
                    # 基本信息
                    st.markdown(f"### {stock_name} ({ts_code})")
                    st.write(f"**行业:** {industry}")
                    st.write(f"**连板天数:** {consecutive_days}天")

                    # 详细K线图（更大尺寸）
                    detail_fig = plot_enhanced_kline(df, ts_code, days=30)
                    detail_fig.update_layout(height=300)
                    st.plotly_chart(detail_fig, use_container_width=True)

                    # 最近走势数据
                    st.markdown("**最近5日走势:**")
                    recent_data = []
                    for i in range(-5, 0):
                        if len(df) >= abs(i):
                            row = df.iloc[i]
                            prev = df.iloc[i-1] if i > -len(df) else row
                            pct = (row['close'] - prev['close']) / prev['close'] * 100
                            vol_col = 'volume' if 'volume' in df.columns else 'vol'
                            recent_data.append({
                                '日期': row['trade_date'],
                                '收盘价': f"¥{row['close']:.2f}",
                                '涨跌幅': f"{pct:.2f}%",
                                '成交量': f"{row.get(vol_col, 0)/10000:.1f}万"
                            })

                    if recent_data:
                        st.dataframe(pd.DataFrame(recent_data), hide_index=True, use_container_width=True)

                    # 历史涨停记录
                    st.markdown("**近期涨停记录:**")
                    limit_history = limit_service.get_recent_limit_up_history(ts_code, days=60)
                    if limit_history:
                        history_text = ", ".join([f"{date}({days}板)" for date, days in limit_history[-5:]])
                        st.caption(history_text)
                    else:
                        st.caption("近期无涨停记录")

                    # 对比相似股票
                    if ts_code in similarity_map and similarity_map[ts_code]:
                        st.markdown("**与相似股票对比:**")
                        similar = similarity_map[ts_code]

                        for sim_code, score in similar[:2]:
                            sim_name = stock_name_map.get(sim_code, sim_code)
                            sim_df = dm.get_bars(sim_code, 'D')

                            if sim_df is not None and len(sim_df) >= 2:
                                st.markdown(f"#### {sim_name} (相似度: {score:.3f})")

                                # 对比图
                                compare_fig = make_subplots(rows=1, cols=2, subplot_titles=(stock_name, sim_name))

                                # 左侧：当前股票
                                compare_fig.add_trace(go.Scatter(
                                    y=df['close'].tail(CONSECUTIVE_DAYS_TO_SHOW),
                                    mode='lines',
                                    name=stock_name,
                                    line=dict(color='red', width=2)
                                ), row=1, col=1)

                                # 右侧：相似股票
                                compare_fig.add_trace(go.Scatter(
                                    y=sim_df['close'].tail(CONSECUTIVE_DAYS_TO_SHOW),
                                    mode='lines',
                                    name=sim_name,
                                    line=dict(color='blue', width=2)
                                ), row=1, col=2)

                                compare_fig.update_layout(height=250, showlegend=False)
                                st.plotly_chart(compare_fig, use_container_width=True)

    if len(filtered_stocks) > MAX_STOCKS_PER_TIER:
        st.info(f"还有 {len(filtered_stocks) - MAX_STOCKS_PER_TIER} 只股票未显示")

    st.markdown("---")
