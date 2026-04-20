"""数据同步服务"""
from typing import List, Optional
from tqdm import tqdm
from loguru import logger

from src.common.data.data_manager import DataManager
from config.settings import SUPPORTED_FREQS


class SyncService:
    """数据同步服务，负责从网络同步数据到本地"""

    def __init__(self, data_manager: DataManager = None):
        self.data_manager = data_manager or DataManager()
        logger.info("SyncService initialized")

    def sync_stock_list(self, force_update: bool = True) -> int:
        """同步股票列表"""
        logger.info("Starting stock list sync")
        df = self.data_manager.get_stock_list(force_update=force_update)
        count = len(df)
        logger.info(f"Stock list sync completed, {count} stocks")
        return count

    def sync_all_daily(self, skip_existing: bool = True) -> tuple:
        """同步所有股票日线数据"""
        return self.sync_freq('D', skip_existing=skip_existing)

    def sync_freq(
        self,
        freq: str,
        skip_existing: bool = True,
        limit: int = None,
    ) -> tuple:
        """同步指定周期的所有股票数据

        Args:
            freq: 时间周期
            skip_existing: 是否跳过已同步的
            limit: 限制同步数量，用于测试

        Returns:
            (成功数, 失败数)
        """
        if freq not in SUPPORTED_FREQS:
            logger.error(f"Unsupported frequency: {freq}")
            return 0, 0

        # 获取股票列表
        stock_df = self.data_manager.get_stock_list()
        ts_codes = stock_df['ts_code'].tolist()

        if skip_existing:
            # 获取已经同步的状态
            existing = self.data_manager.get_all_local_stocks(freq)
            ts_codes = [t for t in ts_codes if t not in existing]

        if limit is not None and limit > 0:
            ts_codes = ts_codes[:limit]

        total = len(ts_codes)
        if total == 0:
            logger.info(f"No stocks need sync for {freq}")
            return 0, 0

        logger.info(f"Starting sync for {freq}, {total} stocks to sync")

        success = 0
        failed = 0

        # 记录同步开始
        log_id = self.data_manager.sqlite_store.log_sync_start(freq, total)

        try:
            for ts_code in tqdm(ts_codes, desc=f"Syncing {freq}"):
                ok, count = self.data_manager.download_and_save(ts_code, freq)
                if ok:
                    success += 1
                else:
                    failed += 1

                if (success + failed) % 50 == 0:
                    logger.info(f"Sync progress: {success + failed}/{total}, success={success}")

            # 记录同步完成
            self.data_manager.sqlite_store.log_sync_end(
                log_id, success, failed, 'completed'
            )
            logger.info(f"Sync completed for {freq}: success={success}, failed={failed}")

        except Exception as e:
            # 记录错误
            self.data_manager.sqlite_store.log_sync_end(
                log_id, success, failed, 'failed', str(e)
            )
            logger.error(f"Sync interrupted: {e}")
            raise

        return success, failed

    def sync_multiple_freqs(
        self,
        freqs: List[str],
        skip_existing: bool = True,
        limit: int = None,
    ) -> dict:
        """同步多个周期的数据"""
        results = {}

        for freq in freqs:
            if freq not in SUPPORTED_FREQS:
                logger.warning(f"Skipping unsupported freq: {freq}")
                continue

            logger.info(f"=== Starting sync for {freq} ===")
            success, failed = self.sync_freq(freq, skip_existing=skip_existing, limit=limit)
            results[freq] = (success, failed)
            logger.info(f"=== Completed sync for {freq}: {success} success, {failed} failed ===")

        return results

    def update_daily(self) -> tuple:
        """每日增量更新

        只更新有数据更新的股票
        """
        # 对于增量更新，我们简单重新下载所有已经同步过的股票
        # 这样可以获取最新数据
        logger.info("Starting daily update")

        success = 0
        failed = 0

        for freq in ['D']:  # 只更新日线，分钟线一般不需要每日更新
            existing = self.data_manager.get_all_local_stocks(freq)
            logger.info(f"Updating {len(existing)} stocks for {freq}")

            for ts_code in tqdm(existing, desc=f"Updating {freq}"):
                ok, count = self.data_manager.download_and_save(ts_code, freq)
                if ok:
                    success += 1
                else:
                    failed += 1

        logger.info(f"Daily update completed: success={success}, failed={failed}")
        return success, failed

    def get_sync_status(self, freq: str) -> dict:
        """获取同步状态"""
        total_stocks = len(self.data_manager.get_stock_list())
        synced = self.data_manager.get_all_local_stocks(freq)
        return {
            'freq': freq,
            'total_stocks': total_stocks,
            'synced_count': len(synced),
            'sync_percent': round(len(synced) / total_stocks * 100, 2) if total_stocks > 0 else 0,
        }
