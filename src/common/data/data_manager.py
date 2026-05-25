"""数据管理门面 - 统一数据访问接口"""
import pandas as pd
from typing import List, Optional, Tuple, Dict
from loguru import logger

from config.settings import SUPPORTED_FREQS, TUSHARE_TOKEN
from .fetchers.tushare_fetcher import TushareFetcher
from .fetchers.akshare_fetcher import AKShareFetcher
from .fetchers.baostock_fetcher import BaoStockFetcher
from .storage.parquet_store import ParquetStore
from .storage.sqlite_store import SQLiteStore


class DataManager:
    """数据管理门面，协调数据源和存储"""

    def __init__(self):
        # 存储层
        self.parquet_store = ParquetStore()
        self.sqlite_store = SQLiteStore()

        # 数据源 - 优先尝试，失败自动降级
        self.tushare = TushareFetcher() if TUSHARE_TOKEN else None
        self.akshare = AKShareFetcher()
        self.baostock = BaoStockFetcher()

        logger.info("DataManager initialized")

    def get_stock_list(self, force_update: bool = False) -> pd.DataFrame:
        """获取股票列表，从缓存或重新获取"""
        if not force_update:
            df = self.sqlite_store.get_stock_list()
            if not df.empty:
                return df

        # 重新获取
        if self.tushare:
            try:
                df = self.tushare.get_stock_list()
                self.sqlite_store.save_stock_list(df)
                return df
            except Exception as e:
                logger.error(f"Tushare failed: {e}, fallback to AkShare")

        # Tushare失败，尝试AkShare
        try:
            df = self.akshare.get_stock_list()
            self.sqlite_store.save_stock_list(df)
            return df
        except Exception as e:
            logger.error(f"AkShare failed: {e}, fallback to Baostock")

        # AkShare失败，尝试Baostock
        df = self.baostock.get_stock_list()
        self.sqlite_store.save_stock_list(df)
        return df

    def search_stocks(self, keyword: str) -> pd.DataFrame:
        """搜索股票（按名称或代码）"""
        # 先按代码搜索
        result = self.sqlite_store.get_stock_by_symbol(keyword)
        if result is not None:
            return result

        # 再按名称搜索
        result = self.sqlite_store.get_stock_by_name(keyword)
        if result is not None:
            return result

        return pd.DataFrame()

    def resample_bars(self, df_daily: pd.DataFrame, freq: str) -> Optional[pd.DataFrame]:
        """从日线数据合成其他长周期（周/月/季/年）

        Args:
            df_daily: 日线数据
            freq: 目标周期 W/M/Q/Y

        Returns:
            合成后的K线数据
        """
        if df_daily is None or df_daily.empty:
            return None

        if 'trade_date' not in df_daily.columns:
            logger.warning("trade_date column not found, cannot resample")
            return None

        # 映射：周期代码 -> pandas resample 规则
        freq_map = {
            'W': 'W-FRI',       # 周K（周五为结束日）
            'M': 'ME',          # 月K (Month End)
            'Q': 'QE',          # 季K (Quarter End)
            'Y': 'YE',          # 年K (Year End)
            '60min': '60min',   # 60分钟（需要分钟数据合成）
            '30min': '30min',
            '15min': '15min',
        }

        rule = freq_map.get(freq)
        if rule is None:
            logger.warning(f"Unsupported resample freq: {freq}")
            return None

        # 确保 trade_date 是日期类型并设为索引
        df = df_daily.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df = df.set_index('trade_date')

        # 按周期重采样
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
        }
        # 兼容不同的成交量列名
        if 'vol' in df.columns:
            agg_dict['vol'] = 'sum'
        if 'volume' in df.columns:
            agg_dict['volume'] = 'sum'

        resampled = df.resample(rule, label='right', closed='right').agg(agg_dict)

        # 去除空值
        resampled = resampled.dropna()

        # 将索引转回字符串格式的交易日期（YYYYMMDD）
        resampled = resampled.reset_index()
        resampled['trade_date'] = resampled['trade_date'].dt.strftime('%Y%m%d')

        # 添加股票代码列
        if 'ts_code' in df.columns:
            resampled['ts_code'] = df['ts_code'].iloc[0]

        return resampled

    def get_bars(self, ts_code: str, freq: str) -> Optional[pd.DataFrame]:
        """获取K线数据，从本地存储加载

        自动合成逻辑：
        - 如果目标周期本地不存在，但日线存在，从日线自动合成
        - 支持：W周 / M月 / Q季 / Y年
        """
        # 先尝试从本地存储直接加载
        df = self.parquet_store.load(ts_code, freq)
        if df is not None and not df.empty:
            return df

        # 本地没有，尝试从日线合成（仅支持长周期）
        RESAMPLEABLE_FREQS = {'W', 'M', 'Q', 'Y'}
        if freq in RESAMPLEABLE_FREQS:
            # 先加载日线
            df_daily = self.parquet_store.load(ts_code, 'D')
            if df_daily is not None and not df_daily.empty:
                # 从日线合成
                resampled_df = self.resample_bars(df_daily, freq)
                if resampled_df is not None and not resampled_df.empty:
                    # 缓存到磁盘，下次直接读取
                    self.parquet_store.save(resampled_df, ts_code, freq)
                    return resampled_df

        return df

    def get_price_series(self, ts_code: str, freq: str, column: str = 'close') -> Optional[pd.Series]:
        """获取价格序列（用于相似度计算）"""
        df = self.get_bars(ts_code, freq)
        if df is None or df.empty:
            return None

        if column not in df.columns:
            logger.warning(f"Column {column} not found in {ts_code} {freq}")
            return None

        return df[column].reset_index(drop=True)

    def download_and_save(self, ts_code: str, freq: str) -> Tuple[bool, int]:
        """从网络下载并保存数据 - 支持真正的增量更新"""
        symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code

        if freq not in SUPPORTED_FREQS:
            logger.error(f"Unsupported frequency: {freq}")
            return False, 0

        # 读取本地已有数据，用于增量更新
        existing_df = self.get_bars(ts_code, freq)
        has_existing = existing_df is not None and not existing_df.empty

        # ========== 增量更新：只下载本地最新日期之后的数据 ==========
        start_date_yyyymmdd = None  # Tushare/AkShare格式: 20260520
        start_date_iso = None       # Baostock格式: 2026-05-20

        if has_existing and 'trade_date' in existing_df.columns:
            local_latest = str(existing_df['trade_date'].iloc[-1])
            logger.debug(f"{ts_code} {freq} local latest: {local_latest}")

            if len(local_latest) == 8:  # YYYYMMDD
                start_date_yyyymmdd = local_latest
                start_date_iso = f"{local_latest[:4]}-{local_latest[4:6]}-{local_latest[6:8]}"
            else:
                start_date_iso = local_latest
                start_date_yyyymmdd = local_latest.replace('-', '')

        df = None

        # 尝试Tushare
        if self.tushare and self.tushare.token:
            try:
                if freq in ['D', 'W', 'M']:
                    # Tushare接受YYYYMMDD格式
                    df = self.tushare.get_daily_bars(ts_code, start_date=start_date_yyyymmdd)
                else:
                    df = self.tushare.get_minute_bars(ts_code, freq)
            except Exception as e:
                logger.warning(f"Tushare download failed for {ts_code} {freq}: {e}")

        # Tushare失败，尝试AkShare
        if df is None or df.empty:
            try:
                if freq in ['D', 'W', 'M', 'Q', 'Y']:
                    # AkShare接受YYYYMMDD格式
                    df = self.akshare.get_daily_bars(symbol, start_date=start_date_yyyymmdd)
                else:
                    # 分钟线也使用AkShare降级
                    df = self.akshare.get_minute_bars(symbol, freq)
            except Exception as e:
                logger.warning(f"AkShare download failed for {ts_code} {freq}: {e}")

        # AkShare失败，尝试Baostock（仅支持长周期）
        if (df is None or df.empty) and freq in ['D', 'W', 'M', 'Q', 'Y']:
            try:
                # Baostock接受YYYY-MM-DD格式
                df = self.baostock.get_daily_bars(ts_code, start_date=start_date_iso)
            except Exception as e:
                logger.warning(f"Baostock download failed for {ts_code} {freq}: {e}")

        if df is None or df.empty:
            logger.warning(f"No data obtained for {ts_code} {freq}")
            return False, 0

        # ========== 关键修复：增量合并 ==========
        if has_existing:
            # 合并已有数据和新下载的数据，按日期去重
            df = pd.concat([existing_df, df], ignore_index=True)
            # 按交易日期去重，保留最新的
            if 'trade_date' in df.columns:
                df = df.drop_duplicates(subset=['trade_date'], keep='last')
                # 按日期排序
                df = df.sort_values('trade_date').reset_index(drop=True)
            else:
                df = df.drop_duplicates(keep='last')

        # 保存到存储
        success = self.parquet_store.save(df, ts_code, freq)
        if not success:
            return False, 0

        # 更新同步状态
        start_date = str(df['trade_date'].iloc[0]) if 'trade_date' in df.columns else ''
        end_date = str(df['trade_date'].iloc[-1]) if 'trade_date' in df.columns else ''
        self.sqlite_store.update_sync_status(ts_code, freq, start_date, end_date, len(df))

        logger.debug(f"Downloaded and saved {ts_code} {freq}: {len(df)} bars")
        return True, len(df)

    def get_all_local_stocks(self, freq: str) -> List[str]:
        """获取本地已存储的所有股票代码"""
        return self.parquet_store.get_all_ts_codes(freq)

    def extract_segment(self, df: pd.DataFrame, start_idx: int, end_idx: int) -> pd.DataFrame:
        """提取指定索引区间的数据"""
        return df.iloc[start_idx:end_idx].copy()

    def is_data_available(self, ts_code: str, freq: str) -> bool:
        """检查数据是否已在本地可用

        对于W/M/Q/Y长周期，如果日线数据存在，也视为可用（可以自动合成）
        """
        # 先检查目标周期文件是否存在
        if self.parquet_store.exists(ts_code, freq):
            return True

        # 长周期可以从日线合成
        RESAMPLEABLE_FREQS = {'W', 'M', 'Q', 'Y'}
        if freq in RESAMPLEABLE_FREQS:
            # 检查日线是否存在
            return self.parquet_store.exists(ts_code, 'D')

        return False

    def get_sync_status_for_all(self, freq: str) -> dict:
        """获取指定周期所有股票的同步状态"""
        return self.sqlite_store.get_sync_status_map(freq)

    def get_storage_stats(self) -> dict:
        """获取存储统计信息

        Returns:
            字典结构：
            {
                'total_size_mb': float,
                'total_file_count': int,
                'by_freq': {
                    'D': {'count': int, 'size_mb': float},
                    'W': {'count': int, 'size_mb': float},
                    ...
                }
            }
        """
        stats = {
            'total_size_mb': 0,
            'total_file_count': 0,
            'by_freq': {}
        }

        for freq in SUPPORTED_FREQS:
            freq_dir = self.parquet_store.base_dir / freq
            if freq_dir.exists():
                files = list(freq_dir.glob('*.parquet'))
                total_size = sum(f.stat().st_size for f in files)
                stats['by_freq'][freq] = {
                    'count': len(files),
                    'size_mb': total_size / 1024 / 1024
                }
                stats['total_size_mb'] += stats['by_freq'][freq]['size_mb']
                stats['total_file_count'] += len(files)
            else:
                stats['by_freq'][freq] = {'count': 0, 'size_mb': 0}

        return stats

    def get_data_freshness_heatmap(self, days: int = 30, sample_size: int = 100) -> dict:
        """获取数据新鲜度热力图数据

        Args:
            days: 最近多少天
            sample_size: 抽样检查的股票数量

        Returns:
            {date_str: count} 字典，表示每个日期有多少股票有数据
        """
        from datetime import datetime, timedelta

        heatmap = {}
        today = datetime.now()

        # 初始化最近N天的日期
        for days_ago in range(days):
            date = today - timedelta(days=days_ago)
            date_str = date.strftime('%Y%m%d')
            heatmap[date_str] = 0

        # 抽样检查股票数据
        all_stocks = self.get_all_local_stocks('D')
        sample = all_stocks[:sample_size]

        for ts_code in sample:
            df = self.get_bars(ts_code, 'D')
            if df is not None and not df.empty:
                # 检查最近N天的数据
                for date_str in heatmap.keys():
                    if (df['trade_date'] == date_str).any():
                        heatmap[date_str] += 1

        return heatmap

    def check_data_quality(self, freq: str = 'D', sample_size: int = 500) -> dict:
        """检查数据质量

        Args:
            freq: 检查的周期
            sample_size: 抽样检查的股票数量

        Returns:
            {
                'missing_trading_days': [{'ts_code': str, 'missing_count': int}, ...],
                'empty_files': [str, ...],
                'price_anomalies': [{'ts_code': str, 'anomaly_count': int}, ...],
                'stale_data': [{'ts_code': str, 'days_old': int}, ...],
                'summary': {
                    'total_checked': int,
                    'healthy': int,
                    'issues': int
                }
            }
        """
        from datetime import datetime

        issues = {
            'missing_trading_days': [],
            'empty_files': [],
            'price_anomalies': [],
            'stale_data': [],
            'summary': {
                'total_checked': 0,
                'healthy': 0,
                'issues': 0
            }
        }

        all_stocks = self.get_all_local_stocks(freq)
        sample = all_stocks[:sample_size]
        issues['summary']['total_checked'] = len(sample)

        for ts_code in sample:
            df = self.get_bars(ts_code, freq)
            has_issue = False

            # 检查空文件
            if df is None or df.empty:
                issues['empty_files'].append(ts_code)
                has_issue = True
                continue

            # 检查缺失交易日（仅对日线）
            if freq == 'D' and 'trade_date' in df.columns:
                try:
                    dates = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                    date_range = pd.bdate_range(dates.min(), dates.max())
                    missing = set(date_range) - set(dates)
                    if len(missing) > 5:  # 超过5个工作日缺失
                        issues['missing_trading_days'].append({
                            'ts_code': ts_code,
                            'missing_count': len(missing)
                        })
                        has_issue = True
                except Exception:
                    pass  # 日期格式问题，跳过

            # 检查价格异常（单日涨跌超过30%）
            if 'close' in df.columns:
                try:
                    pct_change = df['close'].pct_change().abs()
                    anomalies = pct_change[pct_change > 0.3]
                    if not anomalies.empty:
                        issues['price_anomalies'].append({
                            'ts_code': ts_code,
                            'anomaly_count': len(anomalies)
                        })
                        has_issue = True
                except Exception:
                    pass

            # 检查数据新鲜度
            if 'trade_date' in df.columns and not df.empty:
                try:
                    last_date = str(df['trade_date'].iloc[-1])
                    if len(last_date) == 8:  # YYYYMMDD
                        days_old = (datetime.now() - datetime.strptime(last_date, '%Y%m%d')).days
                    else:  # YYYY-MM-DD
                        days_old = (datetime.now() - datetime.strptime(last_date, '%Y-%m-%d')).days

                    if days_old > 7:
                        issues['stale_data'].append({
                            'ts_code': ts_code,
                            'days_old': days_old
                        })
                        has_issue = True
                except Exception:
                    pass

            if has_issue:
                issues['summary']['issues'] += 1
            else:
                issues['summary']['healthy'] += 1

        return issues
