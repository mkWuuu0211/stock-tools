# 📊 stock-tools - 开源股票分析工具集合

一个可扩展的Python股票分析工具集合，当前包含**形态相似性选股工具**，后续可以方便添加更多子工具。

## 简介

- 🔍 **形态相似性选股** - 根据选定股票的特定时间周期，在沪深全市场历史数据中找出形态相似的股票。支持多种时间维度（日线、周线、月线、15分钟、30分钟、60分钟等）。

## 项目结构

```
stock-tools/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config/                 # 全局配置
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── common/             # 公共基础设施
│   │   ├── __init__.py
│   │   └── data/           # 公共数据访问层
│   │       ├── fetchers/    # 数据源适配器（Tushare/AkShare/Baostock）
│   │       ├── storage/    # 存储引擎（Parquet/SQLite）
│   │       └── data_manager.py
│   └── pattern_matcher/    # 形态相似性选股工具
│       ├── __init__.py
│       ├── algorithm/      # 核心算法
│       │   ├── preprocessor.py
│       │   ├── similarity.py
│       │   ├── features.py
│       │   └── matcher.py
│       └── service/        # 业务服务
│           ├── pattern_service.py
│           └── sync_service.py
├── web/                   # Streamlit Web界面
│   ├── app.py             # 主入口（多工具导航）
│   └── pages/             # 各个工具页面
├── scripts/               # 工具脚本
│   ├── sync_all_data.py    # 全量数据同步
│   └── update_daily.py     # 每日增量更新
├── data/                  # 数据存储目录（自动创建，已加入gitignore）
│   ├── stock_metadata.db  # SQLite元数据库（股票列表、同步状态、进度）
│   └── processed/         # 处理后的行情数据
│       └── D/            # 日线数据（每只股票一个Parquet文件）
└── tests/
```

## ✨ 功能特点

### 🔍 形态相似性选股
- 支持多种时间周期：1min、5min、15min、30min、60min、日线、周线、月线、季线、年线
- 三级匹配算法：皮尔逊快速过滤 → DTW动态时间规整 → 形态特征验证
- 交互式Web界面，直观对比形态相似性
- 支持滑动窗口匹配，可在长序列中寻找最佳匹配段
- 多进程并行计算，加速全市场匹配

### 📊 后台数据同步
- ✅ **不中断同步**：数据同步在独立后台进程运行，刷新/关闭浏览器不中断
- ✅ **进度持久化**：同步进度实时保存到数据库，跨会话可见
- ✅ **自动刷新**：页面每3秒自动刷新进度（可手动开关）
- ✅ **智能降级**：Tushare → AkShare → Baostock 多级数据源自动降级
- ✅ **长周期自动合成**：周/月/季/年线自动从日线合成，无需单独下载

### 📈 K线图可视化
- 标准OHLC蜡烛图（红涨绿跌）
- 成交量副图
- MA5/MA10/MA20/MA60均线可开关
- 支持所有时间周期切换
- 支持显示最近N条或全部历史数据
- 可展开查看原始数据表格

## 算法说明

### 三级匹配策略
1. **一级过滤**：皮尔逊相关系数快速过滤掉80%不相似股票，O(n)复杂度
2. **二级精配**：FastDTW动态时间规整，处理时间偏移，支持不同长度序列匹配
3. **三级验证**：形态特征向量匹配（趋势特征、波动特征、量能特征）

### 综合评分公式
```
最终得分 = 0.4 * 皮尔逊系数 + 0.4 * (1 - 归一化DTW距离) + 0.2 * 特征余弦相似度
```

得分范围 [0, 1]，越接近1越相似。

## 环境要求

- Python 3.8+
- 约5-10GB磁盘空间存储全市场日线数据
- 推荐8GB以上内存

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/stock-tools.git
cd stock-tools
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

**注意**: TA-Lib安装可能需要系统依赖：

- Ubuntu/Debian: `sudo apt-get install ta-lib`
- Mac: `brew install ta-lib`
- Windows: 可以从 [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) 下载预编译whl包安装

### 4. 配置 Tushare Token

1. 注册 [Tushare](https://tushare.pro/) 获取token
2. 复制 `.env.example` 到 `.env`
3. 在 `.env` 中填入你的 Tushare token

```bash
cp .env.example .env
# 编辑 .env 文件
```

如果没有Tushare token，程序会自动降级使用AkShare + Baostock免费数据源，也可以使用，只支持日线数据。

## 使用方法

### 第一步：同步数据

首次使用必须先同步数据：

```bash
# 测试同步前100只日线
python scripts/sync_all_data.py --freqs D --limit 100

# 全量同步所有日线
python scripts/sync_all_data.py --freqs D

# 同步多个周期
python scripts/sync_all_data --freqs D,W,15min
```

或者通过Web界面同步：
```bash
streamlit run web/app.py
```
在数据管理页面选择周期点击开始同步。

### 第二步：启动Web界面

```bash
streamlit run web/app.py --server.address 0.0.0.0
```

浏览器访问 http://localhost:8515

### 第三步：使用功能

在左侧导航栏选择功能页面：

- **📥 数据管理** - 后台同步股票数据，进度持久化
- **🔍 形态相似性选股** - 全市场形态匹配
- **📈 K线图展示** - 单只股票K线可视化

**形态匹配使用流程：**
1. 选择目标股票
2. 选择时间周期
3. 滑动条选择目标形态区间
4. 点击开始匹配
5. 查看相似形态对比图表

## 性能优化

- 分层过滤：先用快算法过滤，慢算法只计算候选
- 多进程并行：利用多个CPU核心同时计算
- Numba加速：热点循环JIT编译
- 按需加载：只加载需要的数据到内存

全市场约5000+只股票，完整匹配通常在 **10-30秒** 完成（取决于CPU核心数）。

## 数据源

- [Tushare](https://tushare.pro/) - 主要数据源，需要token
- [AkShare](https://akshare.xyz/) - 备选免费数据源
- [Baostock](http://baostock.com/) - 备选免费数据源

## 数据更新

建议每日收盘后运行：
```bash
python scripts/update_daily.py
```

## 许可证

MIT
