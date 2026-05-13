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

- 🔍 **形态相似性选股**
- 📥 **数据管理**

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

- 🔍 **形态相似性选股** - 根据选定股票形态找出全市场相似形态的股票
- 📥 **数据管理** - 同步和管理股票历史数据

### 使用说明

1. 在左侧导航栏选择工具
2. 首次使用请先到「数据管理」同步数据
3. 然后使用「形态相似性选股」进行匹配

### 项目主页

https://github.com/mkWuuu0211/stock-tools
""")

# 快速开始
st.markdown("---")
st.subheader("🚀 快速开始")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**第一步**\n\n点击左侧「数据管理」")
with col2:
    st.info("**第二步**\n\n选择周期并同步数据")
with col3:
    st.info("**第三步**\n\n点击「形态相似性选股」开始匹配")

# 页脚
st.markdown("---")
st.caption("💡 stock-tools - 开源股票分析工具集合")
