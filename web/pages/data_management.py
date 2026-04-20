"""数据管理页面"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config.settings import SUPPORTED_FREQS
from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService

# 初始化
st.set_page_config(
    page_title="数据管理 - 股票工具集合",
    page_icon="📊",
    layout="wide",
)

st.title("📊 数据管理")

# 初始化服务
@st.cache_resource
def init_services():
    dm = DataManager()
    sync_service = SyncService(dm)
    return dm, sync_service


dm, sync_service = init_services()

# 显示同步状态
st.subheader("当前同步状态")

for freq, name in SUPPORTED_FREQS.items():
    status = sync_service.get_sync_status(freq)
    progress = status['sync_percent']
    st.write(f"**{name} ({freq})**: {status['synced_count']} / {status['total_stocks']} ({progress}%)")
    st.progress(progress / 100)

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

st.warning("⚠️ 全量同步可能需要较长时间，请耐心等待。日线全量同步大约需要10-30分钟。")

if st.button("🔄 开始同步", type="primary", use_container_width=True):
    with st.spinner("正在同步数据..."):
        # 先同步股票列表
        st.info("同步股票列表...")
        count = sync_service.sync_stock_list(force_update=True)
        st.success(f"股票列表同步完成: {count} 只股票")

        # 同步各个周期
        results = sync_service.sync_multiple_freqs(
            selected_freqs,
            skip_existing=not force_resync,
            limit=limit if limit > 0 else None
        )

        st.markdown("### 同步结果")
        for freq, (success, failed) in results.items():
            st.success(f"**{freq}**: {success} 成功, {failed} 失败")

        st.success("同步完成！请刷新页面查看最新状态")

# 每日更新
st.markdown("---")
st.subheader("每日增量更新")
if st.button("🔄 更新最新日线数据", use_container_width=True):
    with st.spinner("正在更新..."):
        success, failed = sync_service.update_daily()
        st.success(f"更新完成: {success} 成功, {failed} 失败")

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
