"""数据管理页面"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from config.settings import SUPPORTED_FREQS
from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService

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
    return dm, sync_service


dm, sync_service = init_services()

# ========== 🔔 首先检查是否有正在进行的同步 ==========
from datetime import datetime, timedelta
running_syncs = dm.sqlite_store.get_all_running_syncs()

# 超时检测：超过5分钟没更新的running状态视为失效
valid_running_syncs = []
for sync in running_syncs:
    try:
        last_update = datetime.fromisoformat(sync['last_update'])
        if datetime.now() - last_update < timedelta(minutes=5):
            valid_running_syncs.append(sync)
        else:
            st.warning(f"⚠️ 检测到超时的同步任务（{sync['freq']}），已自动标记为失败")
    except:
        pass

# 自动刷新开关（放在顶部，用户可选择）
auto_refresh = True
if valid_running_syncs:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"🔄 后台有 {len(valid_running_syncs)} 个同步任务正在进行")
    with col2:
        auto_refresh = st.checkbox("自动刷新进度", value=True, help="每3秒自动刷新页面更新进度")

# ========== 📊 当前同步状态 ==========
st.subheader("📊 当前同步状态")

status_cols = st.columns(len(SUPPORTED_FREQS))
for idx, (freq, name) in enumerate(SUPPORTED_FREQS.items()):
    with status_cols[idx]:
        status = sync_service.get_sync_status(freq)
        progress = status['sync_percent']

        # 根据进度显示颜色图标
        if progress >= 100:
            icon = "✅"
        elif progress > 0:
            icon = "🔄"
        else:
            icon = "⭕"

        st.metric(
            label=f"{icon} {name}",
            value=f"{progress:.1f}%",
            delta=f"{status['synced_count']} / {status['total_stocks']}"
        )

st.markdown("---")

# 快捷跳转栏
st.subheader("⚡ 快捷跳转")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📈 查看K线图", use_container_width=True):
        st.switch_page("pages/3_📈_K线图展示.py")
with col2:
    if st.button("🔍 形态选股", use_container_width=True):
        st.switch_page("pages/2_🔍_形态相似性选股.py")
with col3:
    if st.button("⚙️ 系统配置", use_container_width=True):
        st.switch_page("pages/4_⚙️_系统配置.py")

st.markdown("---")

# 同步操作
st.subheader("同步数据")

# 选择要同步的周期
selected_freqs = st.multiselect(
    "选择要同步的时间周期",
    options=list(SUPPORTED_FREQS.keys()),
    default=['D'],
    format_func=lambda x: f"{x} - {SUPPORTED_FREQS[x]}",
)

col1, col2 = st.columns(2)
with col1:
    limit = st.number_input("限制同步数量（0表示不限制，测试用）", min_value=0, max_value=5000, value=0)
with col2:
    force_resync = st.checkbox("强制重新同步（覆盖已同步数据）", value=False)

st.info("💡 **周/月/季/年线** 不需要单独下载，会自动从日线数据合成（速度提升 100x+）")
st.warning("⚠️ 日线全量同步可能需要较长时间，请耐心等待。5500只股票大约需要10-30分钟。")

# ========== 依赖检查 ==========
has_daily = 'D' in selected_freqs
has_long_period = any(f in selected_freqs for f in ['W', 'M', 'Q', 'Y'])
has_minute = any(f in selected_freqs for f in ['1min', '5min', '15min', '30min', '60min'])

# 长周期依赖检查
if has_long_period and not has_daily:
    st.error("""
    ⚠️ **依赖检查不通过**

    你选择了周/月/季/年线，但没有选日线！

    长周期K线是**完全从日线数据合成**的，必须先同步日线。
    请同时勾选「D 日线」再开始同步。
    """)
    st.stop()

# 分钟线提示
from config.settings import TUSHARE_TOKEN
if has_minute and not TUSHARE_TOKEN:
    st.warning("""
    ⚠️ **分钟线数据需要Tushare Token**

    你选择了分钟线数据但未配置Tushare Token：
    - 免费数据源（AkShare/Baostock）都不支持历史分钟线
    - 没有Token的情况下分钟线同步会全部失败

    👉 请先去 **「⚙️ 系统配置」** 页面配置Tushare Token
    """)
elif has_minute and TUSHARE_TOKEN:
    st.info("""
    ℹ️ **分钟线数据同步提示**

    已检测到Tushare Token，但请注意：
    - 分钟线数据需要Tushare积分达到120分以上才能获取
    - 如果积分不足，同步仍可能失败

    👉 去 **「⚙️ 系统配置」** 查看详情或更新Token
    """)

# 导入后台同步管理器
from src.pattern_matcher.service.background_sync import get_background_sync_manager
bg_sync_manager = get_background_sync_manager()

if st.button("🔄 开始同步", type="primary", use_container_width=True):
    st.markdown("---")

    # ========== 第一阶段：同步股票列表 ==========
    st.subheader("📋 阶段 1/2: 同步股票列表")
    count = sync_service.sync_stock_list(force_update=True)
    st.success(f"✅ 股票列表同步完成: {count} 只股票")

    st.markdown("---")

    # ========== 第二阶段：启动后台同步 ==========
    st.subheader("📊 阶段 2/2: 启动后台同步")

    # 启动后台同步（不阻塞页面）
    started = bg_sync_manager.start_multiple_syncs(
        freqs=selected_freqs,
        skip_existing=not force_resync,
        limit=limit if limit > 0 else None,
    )

    if started:
        st.success(f"""
        ✅ **后台同步已启动！**

        正在同步: {', '.join([SUPPORTED_FREQS.get(f, f) for f in started])}

        💡 **重要提示：**
        - 你可以**安全地刷新页面**或关闭浏览器，同步会在后台继续运行
        - 回到此页面可以实时查看同步进度
        - 进度会自动每3秒刷新一次
        """)
    else:
        st.warning("没有需要同步的周期，或同步已在运行中")

    st.rerun()  # 立即刷新显示进度

# 每日更新
st.markdown("---")
st.subheader("每日增量更新")
if st.button("🔄 更新最新日线数据", use_container_width=True):
    started = bg_sync_manager.start_sync('D', skip_existing=False)
    if started:
        st.success("✅ 日线增量更新已在后台启动！请查看上方进度")
        st.rerun()
    else:
        st.warning("同步已在进行中")

# ========== 📊 底部同步进度显示 ==========
if valid_running_syncs:
    st.markdown("---")
    st.subheader("📊 同步进度")

    for sync in valid_running_syncs:
        freq_name = SUPPORTED_FREQS.get(sync['freq'], sync['freq'])
        progress = sync['current'] / sync['total'] if sync['total'] > 0 else 0

        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            st.markdown(f"**🟡 {freq_name}**")
        with col2:
            st.markdown(f"进度: {sync['current']} / {sync['total']} ({progress*100:.1f}%)")
        with col3:
            st.markdown(f"成功: {sync['success']} | 失败: {sync['failed']}")
        with col4:
            if st.button(f"❌ 取消同步", key=f"cancel_{sync['freq']}", use_container_width=True):
                dm.sqlite_store.cancel_sync_progress(sync['freq'])
                st.success(f"已取消 {freq_name} 同步")
                st.rerun()
        st.progress(progress)
        st.caption(f"上次更新: {sync['last_update']}")

    # 批量取消按钮
    if len(valid_running_syncs) > 1:
        if st.button("❌ 取消所有正在进行的同步", use_container_width=True):
            dm.sqlite_store.cancel_all_sync_progress()
            st.success("已取消所有正在进行的同步")
            st.rerun()

# ========== 🔄 失败股票重试 ==========
if not valid_running_syncs:
    st.markdown("---")
    st.subheader("🔄 同步失败重试")

    has_failed = False
    for freq in SUPPORTED_FREQS:
        failed_stocks = dm.sqlite_store.get_failed_stocks(freq)
        if failed_stocks:
            has_failed = True
            freq_name = SUPPORTED_FREQS[freq]
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"**{freq_name}** ({freq}) - 上次同步失败 {len(failed_stocks)} 只股票")
                with st.expander("查看失败列表"):
                    for code in failed_stocks[:20]:
                        st.code(code)
                    if len(failed_stocks) > 20:
                        st.caption(f"... 还有 {len(failed_stocks) - 20} 只")
            with col2:
                if st.button(f"🔄 重试 {freq_name}", key=f"retry_{freq}", use_container_width=True):
                    started = bg_sync_manager.retry_failed_stocks(freq)
                    if started:
                        st.success("已启动后台重试已启动！")
                        st.rerun()
                    else:
                        st.warning("启动失败，可能有同步正在运行")

    if not has_failed:
        st.success("✅ 没有同步失败的股票")

# ========== 🔄 自动刷新机制 ==========
if valid_running_syncs and auto_refresh:
    import time
    time.sleep(3)
    st.rerun()

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
