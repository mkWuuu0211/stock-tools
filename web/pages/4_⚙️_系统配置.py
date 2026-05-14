"""系统配置页面"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="系统配置 - 股票工具集合",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚙️ 系统配置")
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
    if st.button("🔍 形态选股", use_container_width=True):
        st.switch_page("pages/2_🔍_形态相似性选股.py")

st.markdown("---")

# 环境变量文件路径
env_path = Path(__file__).parent.parent.parent / ".env"

# 读取当前配置
def read_env():
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        config = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        return config
    return {}

# 保存配置
def save_env(config):
    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    # 更新或添加配置
    new_lines = []
    updated_keys = set()

    for line in lines:
        original_line = line
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key = line.split('=', 1)[0].strip()
            if key in config:
                new_lines.append(f"{key}={config[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(original_line)

    # 添加新配置
    for key, value in config.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

current_config = read_env()

# ========== 数据源配置状态 ==========
st.subheader("📊 数据源配置状态")

col1, col2, col3 = st.columns(3)

with col1:
    tushare_token = current_config.get('TUSHARE_TOKEN', '')
    if tushare_token:
        masked_token = tushare_token[:4] + '*' * (len(tushare_token) - 8) + tushare_token[-4:]
        st.success(f"✅ Tushare Token 已配置")
        st.caption(f"Token: {masked_token}")
    else:
        st.error("❌ Tushare Token 未配置")
        st.caption("分钟线数据需要Tushare高级积分")

with col2:
    st.info("✅ AkShare 无需配置")
    st.caption("免费开源数据源，支持日线")

with col3:
    st.info("✅ Baostock 无需配置")
    st.caption("免费数据源，支持日线数据")

st.markdown("---")

# ========== Tushare Token 配置 ==========
st.subheader("🔑 Tushare Token 配置")

with st.form("tushare_config"):
    new_token = st.text_input(
        "Tushare Token",
        value=tushare_token,
        type="password",
        placeholder="请输入你的Tushare Token",
        help="注册 https://tushare.pro/ 获取Token，积分达到120可获取分钟线数据"
    )

    submitted = st.form_submit_button("💾 保存配置", type="primary")

    if submitted:
        if new_token:
            save_env({'TUSHARE_TOKEN': new_token})
            st.success("✅ Token 已保存！重启服务后生效")
        else:
            st.warning("请输入有效的Token")

st.markdown("---")

# ========== 数据源能力说明 ==========
st.subheader("📋 数据源能力对照表")

st.table({
    "数据周期": ["日线", "周线", "月线", "季线", "年线", "分钟线"],
    "Tushare (需Token)": ["✅", "✅", "✅", "✅", "✅", "✅(需120积分)"],
    "AkShare (免费)": ["✅", "✅", "✅", "✅", "✅", "❌"],
    "Baostock (免费)": ["✅", "✅", "✅", "✅", "✅", "❌"],
})

st.markdown("""
### 💡 使用建议

1. **没有Tushare Token**：
   - 只同步日线数据即可
   - 周/月/季/年线会自动从日线数据合成
   - 不要尝试同步分钟线，会全部失败

2. **有Tushare Token但积分不足**：
   - 可以获取日线数据
   - 分钟线可能仍然失败（需要120积分）

3. **有Tushare Token且积分充足**：
   - 可以同步所有周期数据
   - 包括1min/5min/15min/30min/60min
""")

st.markdown("---")

# ========== 获取Token指引 ==========
with st.expander("📖 如何获取Tushare Token？"):
    st.markdown("""
    1. 访问 [Tushare官网](https://tushare.pro/) 注册账号
    2. 登录后在 个人中心 -> 接口Token 查看你的token
    3. 积分要求：
       - 基础积分（20分）：可获取日线数据
       - 120积分以上：可获取分钟线数据
    4. 积分获取方式：
       - 新用户注册即送20分
       - 邀请好友注册可获得积分
       - 参与社区贡献可获得积分
    """)
