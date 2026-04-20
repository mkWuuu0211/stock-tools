"""全局配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

# 创建数据目录
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 数据源配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 数据库配置
SQLITE_DB_PATH = ROOT_DIR / "data" / "stock_metadata.db"

# Redis配置（可选）
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"

# 支持的时间周期
SUPPORTED_FREQS = {
    "1min": "1分钟",
    "5min": "5分钟",
    "15min": "15分钟",
    "30min": "30分钟",
    "60min": "60分钟",
    "D": "日线",
    "W": "周线",
    "M": "月线",
}

# 算法参数配置
# 三级过滤阈值
PEARSON_THRESHOLD = 0.5  # 一级过滤：皮尔逊相关系数阈值
MAX_CANDIDATES_AFTER_FIRST = 500  # 一级过滤后保留候选数
MAX_CANDIDATES_AFTER_SECOND = 100  # 二级过滤后保留候选数

# DTW参数
DTW_RADIUS = 5

# 综合评分权重
WEIGHT_PEARSON = 0.4
WEIGHT_DTW = 0.4
WEIGHT_FEATURE = 0.2

# 并行计算配置
DEFAULT_N_PROCESSES = max(1, os.cpu_count() - 1)

# 缓存配置
RESULTS_CACHE_TTL = 24 * 3600  # 24小时
