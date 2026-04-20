"""模式匹配业务服务"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from loguru import logger

from config.settings import SUPPORTED_FREQS
from src.common.data.data_manager import DataManager
from src.pattern_matcher.algorithm.preprocessor import prepare_series
from src.pattern_matcher.algorithm.matcher import PatternMatcher


class PatternMatchingService:
    """模式匹配服务，协调数据获取和匹配计算"""

    def __init__(self, data_manager: DataManager = None):
        self.data_manager = data_manager or DataManager()
        self.matcher = PatternMatcher()
        logger.info("PatternMatchingService initialized")

    def get_available_freqs(self) -> Dict[str, str]:
        """获取支持的时间周期"""
        return SUPPORTED_FREQS

    def prepare_target(
        self,
        ts_code: str,
        freq: str,
        start_idx: Optional[int] = None,
        end_idx: Optional[int] = None,
        normalization: str = 'minmax',
    ) -> Tuple[Optional[np.ndarray], Optional[pd.DataFrame]]:
        """准备目标序列

        Args:
            ts_code: 目标股票代码
            freq: 时间周期
            start_idx: 起始索引（None表示从头开始）
            end_idx: 结束索引（None表示到结尾）
            normalization: 归一化方法

        Returns:
            (归一化序列, 原始数据DataFrame)
        """
        df = self.data_manager.get_bars(ts_code, freq)
        if df is None or df.empty:
            logger.warning(f"No data available for {ts_code} {freq}")
            return None, None

        # 提取价格序列
        if 'close' not in df.columns:
            logger.error(f"close column not found for {ts_code} {freq}")
            return None, df

        prices = df['close']

        # 截取片段
        if start_idx is not None and end_idx is not None:
            prices = prices.iloc[start_idx:end_idx]
            df = df.iloc[start_idx:end_idx].copy()
        elif start_idx is not None:
            prices = prices.iloc[start_idx:]
            df = df.iloc[start_idx:].copy()
        elif end_idx is not None:
            prices = prices.iloc[:end_idx]
            df = df.iloc[:end_idx].copy()

        # 归一化
        series = prepare_series(prices, method=normalization)

        if len(series) < 3:
            logger.warning(f"Segment too short for {ts_code} {freq}")
            return None, df

        logger.info(f"Prepared target: {ts_code} {freq}, length={len(series)}")
        return series, df

    def collect_candidates(
        self,
        freq: str,
        exclude_target: str = None,
    ) -> Dict[str, np.ndarray]:
        """收集候选序列"""
        candidates = {}
        local_ts_codes = self.data_manager.get_all_local_stocks(freq)

        for ts_code in local_ts_codes:
            if exclude_target and ts_code == exclude_target:
                continue

            series = self.data_manager.get_price_series(ts_code, freq, 'close')
            if series is None or len(series) < 5:
                continue

            # 归一化
            norm_series = prepare_series(series, method='minmax')
            if len(norm_series) >= 5:
                candidates[ts_code] = norm_series

        logger.info(f"Collected {len(candidates)} valid candidates for {freq}")
        return candidates

    def match(
        self,
        target_ts_code: str,
        freq: str,
        start_idx: Optional[int] = None,
        end_idx: Optional[int] = None,
        top_k: int = 20,
        use_multiprocessing: bool = True,
        verbose: bool = True,
    ) -> Tuple[Optional[List[Dict]], Optional[pd.DataFrame]]:
        """执行形态匹配

        Args:
            target_ts_code: 目标股票代码
            freq: 时间周期
            start_idx: 目标片段起始索引
            end_idx: 目标片段结束索引
            top_k: 返回多少个Top结果
            use_multiprocessing: 是否使用多进程
            verbose: 是否打印进度

        Returns:
            (匹配结果列表, 目标原始数据)
        """
        # 准备目标序列
        target_series, target_df = self.prepare_target(
            target_ts_code, freq, start_idx, end_idx
        )

        if target_series is None:
            return None, None

        # 收集候选
        candidates = self.collect_candidates(freq, exclude_target=target_ts_code)

        if len(candidates) == 0:
            logger.warning("No candidates available for matching")
            return [], target_df

        # 执行匹配
        results = self.matcher.match_all(
            target_series,
            candidates,
            use_multiprocessing=use_multiprocessing,
            verbose=verbose,
        )

        # 补充股票名称
        stock_list = self.data_manager.get_stock_list()
        for result in results:
            info = stock_list[stock_list['ts_code'] == result['ts_code']]
            if not info.empty:
                result['name'] = info.iloc[0]['name']
            else:
                result['name'] = ''

        # 只返回top_k
        results = results[:top_k]

        logger.info(f"Matching completed, returned {len(results)} results")
        return results, target_df

    def get_match_result_with_data(
        self,
        result: Dict,
        freq: str,
        target_length: int,
    ) -> Optional[pd.DataFrame]:
        """获取匹配结果对应的数据片段"""
        ts_code = result['ts_code']
        start_idx = result['start_idx']

        df = self.data_manager.get_bars(ts_code, freq)
        if df is None or df.empty:
            return None

        if start_idx is not None:
            end_idx = start_idx + target_length
            return df.iloc[start_idx:end_idx].copy()

        return df
