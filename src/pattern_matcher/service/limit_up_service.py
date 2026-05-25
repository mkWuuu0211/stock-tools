"""连板梯队服务 - 数据加载、缓存和相似度分析"""
import os
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from src.common.data.data_manager import DataManager
from src.pattern_matcher.algorithm.detector import LimitUpDetector
from src.pattern_matcher.algorithm.similarity import combined_similarity
from src.pattern_matcher.algorithm.preprocessor import normalize_minmax
from config.settings import CACHE_DIR, CONSECUTIVE_DAYS_TO_SHOW


class LimitUpService:
    """连板梯队服务

    职责：
    1. 批量扫描所有股票检测涨停/跌停
    2. 按连板天数分组
    3. 缓存扫描结果避免重复计算
    4. 计算榜单内股票间的相似度
    """

    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
        self.detector = LimitUpDetector()
        self.cache_dir = CACHE_DIR / 'limit_up'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, date: str) -> Path:
        """获取指定日期的缓存文件路径"""
        return self.cache_dir / f"{date}.pkl"

    def _load_cache(self, date: str) -> Optional[Dict]:
        """从缓存加载扫描结果"""
        cache_path = self._get_cache_path(date)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache for {date}: {e}")
        return None

    def _save_cache(self, date: str, data: Dict):
        """保存扫描结果到缓存"""
        cache_path = self._get_cache_path(date)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"Cached limit-up results for {date}")
        except Exception as e:
            logger.warning(f"Failed to save cache for {date}: {e}")

    def scan_limit_up_on_date(
        self,
        date: str,
        use_cache: bool = True
    ) -> Dict:
        """扫描指定日期的涨停股票

        Args:
            date: 日期字符串，格式 'YYYYMMDD'
            use_cache: 是否使用缓存

        Returns:
            字典结构：
            {
                'date': str,
                'stocks': List[Tuple[ts_code, df, result_dict]],
                'total_scanned': int,
                'scan_time': str
            }
        """
        # 尝试从缓存加载
        if use_cache:
            cached = self._load_cache(date)
            if cached:
                logger.info(f"Loaded cached limit-up results for {date}")
                return cached

        # 获取所有本地有数据的股票
        all_stocks = self.dm.get_all_local_stocks('D')
        logger.info(f"Scanning {len(all_stocks)} stocks for limit-up on {date}")

        # 批量加载数据并检测
        data_dict = {}
        for ts_code in all_stocks:
            df = self.dm.get_bars(ts_code, 'D')
            if df is not None and not df.empty:
                data_dict[ts_code] = df

        # 批量检测涨停
        limit_up_stocks = self.detector.batch_detect_limit_up(data_dict, date)

        # 构建结果
        result = {
            'date': date,
            'stocks': limit_up_stocks,
            'total_scanned': len(all_stocks),
            'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 保存到缓存
        self._save_cache(date, result)

        return result

    def get_limit_up_tiers(self, date: str) -> Dict[str, List]:
        """获取连板梯队分组

        Args:
            date: 日期字符串

        Returns:
            字典结构：
            {
                '1': [(ts_code, df, result), ...],  # 首板
                '2': [...],                          # 2连板
                '3': [...],                          # 3连板
                '4+': [...]                          # 4板及以上
            }
        """
        scan_result = self.scan_limit_up_on_date(date)

        tiers = {
            '1': [],  # 首板
            '2': [],  # 2连板
            '3': [],  # 3连板
            '4+': []  # 4板及以上
        }

        for ts_code, df, result in scan_result['stocks']:
            consecutive_days = result['consecutive_days']

            if consecutive_days == 1:
                tiers['1'].append((ts_code, df, result))
            elif consecutive_days == 2:
                tiers['2'].append((ts_code, df, result))
            elif consecutive_days == 3:
                tiers['3'].append((ts_code, df, result))
            else:
                tiers['4+'].append((ts_code, df, result))

        return tiers

    def calculate_similarity_in_group(
        self,
        stocks: List[Tuple[str, pd.DataFrame, dict]],
        top_k: int = 5
    ) -> Dict[str, List[Tuple[str, float]]]:
        """计算分组内股票间的相似度

        Args:
            stocks: 股票列表 [(ts_code, df, result), ...]
            top_k: 每只股票返回前K个最相似的

        Returns:
            相似度字典：
            {
                'ts_code1': [('similar_ts_code', score), ...],
                'ts_code2': [...],
                ...
            }
        """
        if len(stocks) < 2:
            return {}

        # 提取所有股票的走势序列（最后N天）
        sequences = {}
        for ts_code, df, result in stocks:
            if len(df) >= CONSECUTIVE_DAYS_TO_SHOW:
                seq = df['close'].iloc[-CONSECUTIVE_DAYS_TO_SHOW:].values
                sequences[ts_code] = normalize_minmax(seq)

        # 计算两两相似度
        similarity_map = {}
        ts_codes = list(sequences.keys())

        for i, ts_code1 in enumerate(ts_codes):
            similar_stocks = []
            seq1 = sequences[ts_code1]

            for ts_code2 in ts_codes:
                if ts_code1 == ts_code2:
                    continue

                seq2 = sequences[ts_code2]
                score = combined_similarity(seq1, seq2)
                similar_stocks.append((ts_code2, score))

            # 按相似度降序排序，取前K个
            similar_stocks.sort(key=lambda x: x[1], reverse=True)
            similarity_map[ts_code1] = similar_stocks[:top_k]

        return similarity_map

    def get_stock_info(self, ts_code: str) -> Dict:
        """获取股票基本信息

        Args:
            ts_code: 股票代码

        Returns:
            字典包含 name, industry 等
        """
        stock_list = self.dm.get_stock_list()
        stock_info = stock_list[stock_list['ts_code'] == ts_code]

        if stock_info.empty:
            return {'name': ts_code, 'industry': '未知'}

        row = stock_info.iloc[0]
        return {
            'name': row.get('name', ts_code),
            'industry': row.get('industry', '未知'),
            'area': row.get('area', '未知')
        }

    def get_recent_limit_up_history(self, ts_code: str, days: int = 30) -> List[Tuple[str, int]]:
        """获取股票最近的涨停历史

        Args:
            ts_code: 股票代码
            days: 最近多少天

        Returns:
            列表：[(date, consecutive_days), ...]
        """
        df = self.dm.get_bars(ts_code, 'D')
        if df is None or df.empty:
            return []

        # 取最近N天
        recent_df = df.tail(days)

        history = []
        for idx, row in recent_df.iterrows():
            date = row['trade_date']
            result = self.detector.get_limit_up_stocks_on_date(df, ts_code, date)
            if result and result['is_limit_up']:
                history.append((date, result['consecutive_days']))

        return history
