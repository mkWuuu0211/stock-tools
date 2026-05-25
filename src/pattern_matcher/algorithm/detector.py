"""连板检测器 - 涨停/跌停检测和连板计数"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from config.settings import LIMIT_THRESHOLD, LIMIT_TOLERANCE


class LimitUpDetector:
    """涨停/跌停检测器

    支持不同板块的阈值检测：
    - 主板：±10%
    - 创业板：±20%
    - 科创板：±20%
    - 北交所：±30%
    - ST股票：±5%
    """

    def __init__(self):
        self.thresholds = LIMIT_THRESHOLD
        self.tolerance = LIMIT_TOLERANCE

    def get_board_type(self, ts_code: str) -> str:
        """根据股票代码判断所属板块

        Args:
            ts_code: 股票代码，如 '000001.SZ', '300001.SZ', '688001.SH'

        Returns:
            板块类型：'main', 'chinext', 'star', 'bse', 'st'
        """
        code = ts_code.split('.')[0]

        # ST股票
        if 'ST' in ts_code.upper():
            return 'st'

        # 根据代码前缀判断
        if code.startswith('688') or code.startswith('689'):
            return 'star'  # 科创板
        elif code.startswith('300') or code.startswith('301'):
            return 'chinext'  # 创业板
        elif code.startswith('8') or code.startswith('4'):
            return 'bse'  # 北交所
        else:
            return 'main'  # 主板

    def get_threshold(self, ts_code: str) -> float:
        """获取股票的涨跌停阈值

        Args:
            ts_code: 股票代码

        Returns:
            阈值百分比（小数形式，如 0.10 表示 10%）
        """
        board_type = self.get_board_type(ts_code)
        return self.thresholds[board_type]

    def detect_limit_up(self, df: pd.DataFrame, ts_code: str) -> pd.Series:
        """检测涨停日期

        Args:
            df: K线数据，必须包含 'close' 列
            ts_code: 股票代码

        Returns:
            布尔序列，True 表示该日涨停
        """
        if 'close' not in df.columns or len(df) < 2:
            return pd.Series([False] * len(df), index=df.index)

        threshold = self.get_threshold(ts_code)

        # 计算前一日收盘价
        prev_close = df['close'].shift(1)

        # 计算涨幅
        pct_change = (df['close'] - prev_close) / prev_close

        # 涨停判断：涨幅 >= 阈值 * (1 - tolerance)
        limit_up = pct_change >= threshold * (1 - self.tolerance)

        return limit_up

    def detect_limit_down(self, df: pd.DataFrame, ts_code: str) -> pd.Series:
        """检测跌停日期

        Args:
            df: K线数据，必须包含 'close' 列
            ts_code: 股票代码

        Returns:
            布尔序列，True 表示该日跌停
        """
        if 'close' not in df.columns or len(df) < 2:
            return pd.Series([False] * len(df), index=df.index)

        threshold = self.get_threshold(ts_code)

        # 计算前一日收盘价
        prev_close = df['close'].shift(1)

        # 计算跌幅
        pct_change = (df['close'] - prev_close) / prev_close

        # 跌停判断：跌幅 <= -阈值 * (1 - tolerance)
        limit_down = pct_change <= -threshold * (1 - self.tolerance)

        return limit_down

    def count_consecutive_limit_up(self, df: pd.DataFrame, ts_code: str, end_idx: int = -1) -> int:
        """计算连板天数（从指定日期往前数）

        Args:
            df: K线数据
            ts_code: 股票代码
            end_idx: 结束索引，-1 表示最后一天

        Returns:
            连板天数
        """
        if len(df) < 2:
            return 0

        limit_up_series = self.detect_limit_up(df, ts_code)

        # 处理索引
        if end_idx == -1:
            end_idx = len(df) - 1

        # 从 end_idx 往前数连续的涨停
        count = 0
        for i in range(end_idx, -1, -1):
            if i < len(limit_up_series) and limit_up_series.iloc[i]:
                count += 1
            else:
                break

        return count

    def get_limit_up_stocks_on_date(
        self,
        df: pd.DataFrame,
        ts_code: str,
        date: str
    ) -> Optional[dict]:
        """获取指定日期是否涨停

        Args:
            df: K线数据
            ts_code: 股票代码
            date: 日期字符串，格式 'YYYYMMDD'

        Returns:
            字典 {'is_limit_up': bool, 'is_limit_down': bool, 'consecutive_days': int}
            如果日期不存在返回 None
        """
        if 'trade_date' not in df.columns:
            return None

        # 找到指定日期
        date_mask = df['trade_date'] == date
        if not date_mask.any():
            return None

        date_idx = df[date_mask].index[0]

        limit_up_series = self.detect_limit_up(df, ts_code)
        limit_down_series = self.detect_limit_down(df, ts_code)

        is_limit_up = limit_up_series.iloc[date_idx]
        is_limit_down = limit_down_series.iloc[date_idx]

        # 计算连板天数
        consecutive_days = 0
        if is_limit_up:
            consecutive_days = self.count_consecutive_limit_up(df, ts_code, date_idx)

        return {
            'is_limit_up': is_limit_up,
            'is_limit_down': is_limit_down,
            'consecutive_days': consecutive_days
        }

    def batch_detect_limit_up(
        self,
        data_dict: dict,
        date: str
    ) -> List[Tuple[str, pd.DataFrame, dict]]:
        """批量检测指定日期的涨停股票

        Args:
            data_dict: {ts_code: DataFrame} 字典
            date: 日期字符串，格式 'YYYYMMDD'

        Returns:
            涨停股票列表：[(ts_code, df, result_dict), ...]
        """
        limit_up_stocks = []

        for ts_code, df in data_dict.items():
            result = self.get_limit_up_stocks_on_date(df, ts_code, date)
            if result and result['is_limit_up']:
                limit_up_stocks.append((ts_code, df, result))

        # 按连板天数降序排序
        limit_up_stocks.sort(key=lambda x: x[2]['consecutive_days'], reverse=True)

        return limit_up_stocks
