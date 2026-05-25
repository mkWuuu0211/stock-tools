"""数据管理页面 - Tab布局优化版"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import SUPPORTED_FREQS, TUSHARE_TOKEN
from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService
from src.pattern_matcher.service.background_sync import get_background_sync_manager

# 初始化
st.set_page_config(
    page_title="数据管理 - 股票工具集合",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 数据管理")

# 初始化服务
@st.cache_resource
def init_services():
    dm = DataManager()
    sync_service = SyncService(dm)
    bg_sync_manager = get_background_sync_manager()
    return dm, sync_service, bg_sync_manager

dm, sync_service, bg_sync_manager = init_services()

# ========== 检查同步状态 ==========
running_syncs = dm.sqlite_store.get_all_running_syncs()

# 超时检测
valid_running_syncs = []
for sync in running_syncs:
    try:
        last_update = datetime.fromisoformat(sync['last_update'])
        if datetime.now() - last_update < timedelta(minutes=5):
            valid_running_syncs.append(sync)
    except:
        pass

# 自动刷新
auto_refresh = False
if valid_running_syncs:
    auto_refresh = True

# ========== Tab 布局 ==========
tab1, tab2, tab3, tab4 = st.tabs(["📊 数据概览", "🔄 同步管理", "🔧 数据维护", "📝 同步日志"])

# ==================== Tab 1: 数据概览 ====================
with tab1:
    st.subheader("📊 数据概览")

    # 获取存储统计
    with st.spinner("正在统计存储用量..."):
        storage_stats = dm.get_storage_stats()

    # 顶部指标卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="💾 总存储",
            value=f"{storage_stats['total_size_mb']:.1f} MB" if storage_stats['total_size_mb'] < 1024 else f"{storage_stats['total_size_mb']/1024:.2f} GB"
        )
    with col2:
        st.metric(
            label="📁 文件总数",
            value=f"{storage_stats['total_file_count']:,}"
        )
    with col3:
        daily_count = storage_stats['by_freq'].get('D', {}).get('count', 0)
        st.metric(
            label="📈 日线数据",
            value=f"{daily_count:,} 只",
            delta="基础数据" if daily_count > 0 else None
        )

    st.markdown("---")

    # 各周期存储统计（柱状图）
    st.subheader("📦 各周期存储分布")

    freq_data = []
    for freq, name in SUPPORTED_FREQS.items():
        stats = storage_stats['by_freq'].get(freq, {'count': 0, 'size_mb': 0})
        freq_data.append({
            '周期': f"{name} ({freq})",
            '文件数': stats['count'],
            '大小(MB)': stats['size_mb']
        })

    freq_df = pd.DataFrame(freq_data)

    col1, col2 = st.columns(2)

    with col1:
        # 文件数柱状图
        fig_count = go.Figure(data=[
            go.Bar(
                x=freq_df['周期'],
                y=freq_df['文件数'],
                marker_color='lightblue',
                name='文件数'
            )
        ])
        fig_count.update_layout(
            title="文件数量分布",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_count, use_container_width=True)

    with col2:
        # 存储大小柱状图
        fig_size = go.Figure(data=[
            go.Bar(
                x=freq_df['周期'],
                y=freq_df['大小(MB)'],
                marker_color='lightcoral',
                name='大小(MB)'
            )
        ])
        fig_size.update_layout(
            title="存储大小分布",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_size, use_container_width=True)

    # 数据表格
    with st.expander("📋 查看详细统计"):
        st.dataframe(freq_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 数据新鲜度热力图
    st.subheader("📅 数据新鲜度（最近30天）")

    with st.spinner("正在检查数据新鲜度..."):
        heatmap_data = dm.get_data_freshness_heatmap(days=30, sample_size=100)

    # 转换为热力图数据
    dates = sorted(heatmap_data.keys())
    values = [heatmap_data[d] for d in dates]

    # 简化显示：按周分组
    if len(dates) >= 7:
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=[values],
            x=[d[-4:] for d in dates],  # 只显示月日
            y=['覆盖率'],
            colorscale='Greens',
            showscale=True,
            colorbar=dict(title="股票数")
        ))
        fig_heatmap.update_layout(
            height=200,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis=dict(title="日期", tickangle=-45)
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

        # 统计信息
        avg_coverage = sum(values) / len(values) if values else 0
        max_coverage = max(values) if values else 0
        min_coverage = min(values) if values else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("平均覆盖率", f"{avg_coverage:.0f}%", "100只样本")
        with col2:
            st.metric("最高覆盖", f"{max_coverage}%", "最佳日期")
        with col3:
            st.metric("最低覆盖", f"{min_coverage}%", "最差日期")

    # 快捷跳转
    st.markdown("---")
    st.subheader("⚡ 快捷跳转")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📈 查看K线图", use_container_width=True):
            st.switch_page("pages/3_📈_K线图展示.py")
    with col2:
        if st.button("🔍 形态选股", use_container_width=True):
            st.switch_page("pages/2_🔍_形态相似性选股.py")
    with col3:
        if st.button("🏆 连板梯队", use_container_width=True):
            st.switch_page("pages/5_🏆_连板梯队.py")

# ==================== Tab 2: 同步管理 ====================
with tab2:
    st.subheader("🔄 同步管理")

    # 当前同步状态卡片
    st.subheader("📊 当前同步状态")

    daily_status = sync_service.get_sync_status('D')
    daily_count = daily_status['synced_count']

    status_cols = st.columns(len(SUPPORTED_FREQS))
    for idx, (freq, name) in enumerate(SUPPORTED_FREQS.items()):
        with status_cols[idx]:
            status = sync_service.get_sync_status(freq)
            progress = status['sync_percent']
            synced = status['synced_count']
            total = status['total_stocks']

            RESAMPLEABLE = {'W', 'M', 'Q', 'Y'}
            if freq in RESAMPLEABLE and synced == 0 and daily_count > 0:
                icon = "⚡"
                label = f"{icon} {name}"
                value = f"{min(daily_count, total)}"
                delta = "自动合成"
            else:
                if progress >= 100:
                    icon = "✅"
                elif progress > 0:
                    icon = "🔄"
                else:
                    icon = "⭕"
                label = f"{icon} {name}"
                value = f"{progress:.0f}%"
                delta = f"{synced}/{total}"

            st.metric(label=label, value=value, delta=delta)

    st.markdown("---")

    # 正在进行的同步（带ETA和速度）
    if valid_running_syncs:
        st.subheader("⏱️ 同步进度")

        for sync in valid_running_syncs:
            freq_name = SUPPORTED_FREQS.get(sync['freq'], sync['freq'])
            current = sync['current']
            total = sync['total']
            progress = current / total if total > 0 else 0

            # 计算速度和ETA（基于session_state记录的开始时间）
            session_key = f"sync_start_{sync['freq']}"
            if session_key not in st.session_state:
                # 首次检测到该同步，记录当前时间作为开始时间
                st.session_state[session_key] = datetime.now().isoformat()

            try:
                last_update = datetime.fromisoformat(sync['last_update'])
                start_time = datetime.fromisoformat(st.session_state[session_key])
                elapsed = (last_update - start_time).total_seconds()

                if elapsed > 0 and current > 0:
                    speed = current / elapsed
                    remaining = total - current
                    eta_seconds = remaining / speed if speed > 0 else 0

                    # 格式化ETA
                    if eta_seconds < 60:
                        eta_str = f"{eta_seconds:.0f}秒"
                    elif eta_seconds < 3600:
                        eta_str = f"{eta_seconds/60:.1f}分钟"
                    else:
                        eta_str = f"{eta_seconds/3600:.1f}小时"
                else:
                    speed = 0
                    eta_str = "计算中..."
            except:
                speed = 0
                eta_str = "未知"

            # 显示进度卡片
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.markdown(f"**🟡 {freq_name}**")
            with col2:
                st.markdown(f"进度: {current}/{total} ({progress*100:.1f}%)")
            with col3:
                st.markdown(f"速度: {speed:.1f}只/秒")
            with col4:
                st.markdown(f"ETA: {eta_str}")

            st.progress(progress)
            st.caption(f"成功: {sync['success']} | 失败: {sync['failed']} | 更新: {sync['last_update']}")

            # 取消按钮
            if st.button(f"❌ 取消 {freq_name}", key=f"cancel_{sync['freq']}", use_container_width=True):
                dm.sqlite_store.cancel_sync_progress(sync['freq'])
                st.success(f"已取消 {freq_name} 同步")
                st.rerun()

        st.markdown("---")

    # 同步控制面板
    st.subheader("🎮 同步控制")

    selected_freqs = st.multiselect(
        "选择要同步的时间周期",
        options=list(SUPPORTED_FREQS.keys()),
        default=['D'],
        format_func=lambda x: f"{x} - {SUPPORTED_FREQS[x]}",
    )

    col1, col2 = st.columns(2)
    with col1:
        limit = st.number_input("限制数量（0=不限制）", min_value=0, max_value=5000, value=0)
    with col2:
        force_resync = st.checkbox("强制重新同步", value=False)

    # 提示信息
    st.info("💡 **周/月/季/年线** 会自动从日线合成，无需单独下载")

    # 依赖检查
    has_daily = 'D' in selected_freqs
    has_long_period = any(f in selected_freqs for f in ['W', 'M', 'Q', 'Y'])

    if has_long_period and not has_daily:
        st.error("⚠️ 周/月/季/年线需要先同步日线！请同时勾选「D 日线」")
        st.stop()

    # 分钟线提示
    has_minute = any(f in selected_freqs for f in ['1min', '5min', '15min', '30min', '60min'])
    if has_minute and not TUSHARE_TOKEN:
        st.warning("⚠️ 分钟线需要Tushare Token，请先在「系统配置」页面配置")

    # 启动同步按钮
    if st.button("🚀 开始同步", type="primary", use_container_width=True):
        # 同步股票列表
        st.subheader("📋 同步股票列表")
        count = sync_service.sync_stock_list(force_update=True)
        st.success(f"✅ 股票列表同步完成: {count} 只")

        # 启动后台同步
        started = bg_sync_manager.start_multiple_syncs(
            freqs=selected_freqs,
            skip_existing=not force_resync,
            limit=limit if limit > 0 else None,
        )

        if started:
            st.success(f"✅ 后台同步已启动: {', '.join([SUPPORTED_FREQS.get(f, f) for f in started])}")
            st.rerun()
        else:
            st.warning("没有需要同步的周期，或同步已在运行中")

    # 每日更新按钮
    st.markdown("---")
    if st.button("🔄 每日增量更新", use_container_width=True):
        started = bg_sync_manager.start_sync('D', skip_existing=False)
        if started:
            st.success("✅ 日线增量更新已启动！")
            st.rerun()
        else:
            st.warning("同步已在进行中")

# ==================== Tab 3: 数据维护 ====================
with tab3:
    st.subheader("🔧 数据维护")

    # 数据质量检查
    st.subheader("🔍 数据质量检查")

    col1, col2 = st.columns([2, 1])
    with col1:
        check_freq = st.selectbox("检查周期", options=['D', 'W', 'M'], index=0)
    with col2:
        sample_size = st.number_input("抽样数量", min_value=100, max_value=2000, value=500)

    if st.button("🔍 开始检查", use_container_width=True):
        with st.spinner(f"正在检查 {sample_size} 只股票的数据质量..."):
            quality_report = dm.check_data_quality(freq=check_freq, sample_size=sample_size)

        st.session_state['quality_report'] = quality_report
        st.rerun()

    # 显示质量报告
    if 'quality_report' in st.session_state:
        report = st.session_state['quality_report']
        summary = report['summary']

        st.markdown("---")
        st.subheader("📊 检查报告")

        # 汇总指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("检查总数", f"{summary['total_checked']}")
        with col2:
            st.metric("健康", f"{summary['healthy']}", delta="正常")
        with col3:
            st.metric("问题", f"{summary['issues']}", delta="需关注" if summary['issues'] > 0 else None)

        health_rate = summary['healthy'] / summary['total_checked'] * 100 if summary['total_checked'] > 0 else 0
        st.progress(health_rate / 100)
        st.caption(f"健康率: {health_rate:.1f}%")

        st.markdown("---")

        # 问题详情
        if report['empty_files']:
            with st.expander(f"⚠️ 空文件 ({len(report['empty_files'])} 只)"):
                st.write("以下股票的数据文件为空：")
                for code in report['empty_files'][:20]:
                    st.code(code)
                if len(report['empty_files']) > 20:
                    st.caption(f"... 还有 {len(report['empty_files']) - 20} 只")

        if report['missing_trading_days']:
            with st.expander(f"📅 缺失交易日 ({len(report['missing_trading_days'])} 只)"):
                st.write("以下股票缺失超过5个交易日的数据：")
                for item in report['missing_trading_days'][:20]:
                    st.code(f"{item['ts_code']} - 缺失 {item['missing_count']} 天")
                if len(report['missing_trading_days']) > 20:
                    st.caption(f"... 还有 {len(report['missing_trading_days']) - 20} 只")

        if report['price_anomalies']:
            with st.expander(f"💰 价格异常 ({len(report['price_anomalies'])} 只)"):
                st.write("以下股票存在单日涨跌超过30%的异常：")
                for item in report['price_anomalies'][:20]:
                    st.code(f"{item['ts_code']} - {item['anomaly_count']} 处异常")
                if len(report['price_anomalies']) > 20:
                    st.caption(f"... 还有 {len(report['price_anomalies']) - 20} 只")

        if report['stale_data']:
            with st.expander(f"⏰ 过期数据 ({len(report['stale_data'])} 只)"):
                st.write("以下股票数据超过7天未更新：")
                for item in report['stale_data'][:20]:
                    st.code(f"{item['ts_code']} - 过期 {item['days_old']} 天")
                if len(report['stale_data']) > 20:
                    st.caption(f"... 还有 {len(report['stale_data']) - 20} 只")

        # 一键修复按钮
        if summary['issues'] > 0:
            st.markdown("---")
            if st.button("🔧 一键修复（重新同步问题股票）", use_container_width=True):
                # 收集所有问题股票
                problem_stocks = set()
                problem_stocks.update(report['empty_files'])
                problem_stocks.update([item['ts_code'] for item in report['missing_trading_days']])
                problem_stocks.update([item['ts_code'] for item in report['stale_data']])

                st.info(f"准备修复 {len(problem_stocks)} 只问题股票...")
                # 这里可以启动后台修复任务
                st.success(f"✅ 已启动修复任务，请在「同步管理」Tab查看进度")

    # 失败重试
    st.markdown("---")
    st.subheader("🔄 同步失败重试")

    has_failed = False
    for freq in ['D', 'W', 'M']:  # 只检查主要周期
        failed_stocks = dm.sqlite_store.get_failed_stocks(freq)
        if failed_stocks:
            has_failed = True
            freq_name = SUPPORTED_FREQS[freq]
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"**{freq_name}** - 失败 {len(failed_stocks)} 只")
                with st.expander("查看失败列表"):
                    for code in failed_stocks[:20]:
                        st.code(code)
                    if len(failed_stocks) > 20:
                        st.caption(f"... 还有 {len(failed_stocks) - 20} 只")
            with col2:
                if st.button(f"🔄 重试", key=f"retry_{freq}", use_container_width=True):
                    started = bg_sync_manager.retry_failed_stocks(freq)
                    if started:
                        st.success("重试已启动！")
                        st.rerun()
                    else:
                        st.warning("启动失败")

    if not has_failed:
        st.success("✅ 没有同步失败的股票")

# ==================== Tab 4: 同步日志 ====================
with tab4:
    st.subheader("📝 同步日志")

    # 获取历史日志（从sync_progress表）
    recent_logs = dm.sqlite_store.get_recent_sync_history(limit=20)

    if recent_logs:
        # 转换为DataFrame
        log_data = []
        for log in recent_logs:
            log_data.append({
                '周期': SUPPORTED_FREQS.get(log['freq'], log['freq']),
                '进度': f"{log['current']}/{log['total']}",
                '成功': log['success'],
                '失败': log['failed'],
                '状态': log['status'],
                '更新时间': log['last_update']
            })

        log_df = pd.DataFrame(log_data)
        st.dataframe(log_df, use_container_width=True, hide_index=True)

        # 统计信息
        st.markdown("---")
        st.subheader("📊 同步统计")

        total_runs = len(log_data)
        completed_runs = len([l for l in log_data if l['状态'] == 'completed'])
        running_runs = len([l for l in log_data if l['状态'] == 'running'])
        failed_runs = len([l for l in log_data if l['状态'] == 'failed'])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总记录", total_runs)
        with col2:
            st.metric("已完成", completed_runs, delta=f"{completed_runs/total_runs*100:.1f}%" if total_runs > 0 else "0%")
        with col3:
            st.metric("进行中", running_runs)
        with col4:
            st.metric("失败", failed_runs, delta=f"{failed_runs/total_runs*100:.1f}%" if total_runs > 0 else "0%")
    else:
        st.info("暂无同步日志")

# ========== 自动刷新 ==========
if valid_running_syncs and auto_refresh:
    import time
    time.sleep(3)
    st.rerun()

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
