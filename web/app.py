"""股票工具集合 - Streamlit Web应用主入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# 页面配置
st.set_page_config(
    page_title="股票工具集合",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 侧边栏
st.sidebar.title("📊 股票工具集合")
st.sidebar.markdown("---")

st.sidebar.markdown("""
### 可用工具

- 📥 **数据管理** - 同步和管理股票数据
- 🔍 **形态相似性选股** - 全市场形态匹配
- 📈 **K线图展示** - 股票K线可视化
- 🏆 **连板梯队** - 涨停股票分组和相似度分析
- ⚙️ **系统配置** - 数据源和Token配置

在左侧导航栏选择工具使用
""")

st.sidebar.markdown("---")
st.sidebar.caption("更多工具即将上线...")

# 首页内容
st.title("📊 股票工具集合")
st.markdown("---")

st.write("""
### 欢迎使用股票工具集合

这是一个开源的股票分析工具集合，目前包含：

- 📥 **数据管理** - 后台同步股票历史数据，支持刷新不中断
- 🔍 **形态相似性选股** - 根据选定股票形态找出全市场相似形态的股票
- 📈 **K线图展示** - 专业蜡烛图可视化，支持均线和多周期切换
- ⚙️ **系统配置** - 管理数据源Token和配置

### 快速开始

1. 在左侧导航栏选择「数据管理」
2. 选择「日线」周期，点击开始同步
3. 同步完成后使用「K线图展示」查看数据
4. 使用「形态相似性选股」进行全市场匹配

### 项目主页

https://github.com/mkWuuu0211/stock-tools
""")

# 快速开始
st.markdown("---")
st.subheader("🚀 快速开始")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.info("**第一步**\n\n📥 点击「数据管理」同步日线")
with col2:
    st.info("**第二步**\n\n📈 用「K线图展示」查看数据")
with col3:
    st.info("**第三步**\n\n🔍 用「形态选股」进行匹配")
with col4:
    st.info("**配置**\n\n⚙️ 「系统配置」管理Token")

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
