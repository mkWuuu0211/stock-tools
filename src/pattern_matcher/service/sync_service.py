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

    def resample_all_from_daily(
        self,
        freq: str,
        progress_callback=None,
    ) -> tuple:
        """从已有的日线数据批量合成其他长周期数据

        这比从网络下载快 100x+！

        Args:
            freq: 目标周期 W/M/Q/Y
            progress_callback: 进度回调

        Returns:
            (成功数, 失败数)
        """
        # 获取所有已有日线数据的股票
        daily_stocks = self.data_manager.get_all_local_stocks('D')

        if not daily_stocks:
            logger.warning("No daily data found, cannot resample")
            return 0, 0

        total = len(daily_stocks)
        logger.info(f"Resampling {freq} from daily data for {total} stocks")

        success = 0
        failed = 0

        for ts_code in daily_stocks:
            # 读取日线
            df_daily = self.data_manager.get_bars(ts_code, 'D')
            if df_daily is None or df_daily.empty:
                failed += 1
                if progress_callback:
                    progress_callback(success + failed, total, success, failed)
                continue

            # 合成目标周期
            resampled_df = self.data_manager.resample_bars(df_daily, freq)
            if resampled_df is None or resampled_df.empty:
                failed += 1
            else:
                # 保存到磁盘
                saved = self.data_manager.parquet_store.save(resampled_df, ts_code, freq)
                if saved:
                    # 更新同步状态
                    start_date = str(resampled_df['trade_date'].iloc[0])
                    end_date = str(resampled_df['trade_date'].iloc[-1])
                    self.data_manager.sqlite_store.update_sync_status(
                        ts_code, freq, start_date, end_date, len(resampled_df)
                    )
                    success += 1
                else:
                    failed += 1

            # 进度回调
            if progress_callback:
                progress_callback(success + failed, total, success, failed)

        logger.info(f"Resample completed: {success} success, {failed} failed")
        return success, failed

    def sync_freq(
        self,
        freq: str,
        skip_existing: bool = True,
        limit: int = None,
        progress_callback=None,
        stale_days: int = 3,  # 超过N天没更新的数据才重新同步
    ) -> tuple:
        """同步指定周期的所有股票数据

        对于长周期(W/M/Q/Y)，直接从日线数据批量合成，比网络下载快100x+

        Args:
            freq: 时间周期
            skip_existing: 是否跳过近期已同步的（检查数据新鲜度）
            limit: 限制同步数量，用于测试
            progress_callback: 进度回调函数，参数为 (current, total, success, failed)
            stale_days: 数据超过N天没更新视为过期，需要重新同步

        Returns:
            (成功数, 失败数)
        """
        if freq not in SUPPORTED_FREQS:
            logger.error(f"Unsupported frequency: {freq}")
            return 0, 0

        # ========== 长周期：直接从日线合成，跳过网络下载 ==========
        RESAMPLEABLE_FREQS = {'W', 'M', 'Q', 'Y'}
        if freq in RESAMPLEABLE_FREQS:
            logger.info(f"Resampling {freq} from daily data (faster!)")

            # 检查是否有日线数据
            daily_stocks = self.data_manager.get_all_local_stocks('D')
            if not daily_stocks:
                logger.warning(f"No daily data found! Cannot resample {freq}. Please sync D first.")
                raise RuntimeError("⚠️ 没有找到日线数据！长周期K线依赖日线数据，请先同步日线。")

            return self.resample_all_from_daily(freq, progress_callback)

        # 获取股票列表
        stock_df = self.data_manager.get_stock_list()
        ts_codes = stock_df['ts_code'].tolist()

        if skip_existing:
            # ========== 修复：检查数据新鲜度，不是简单跳过 ==========
            # 获取已同步股票的最新日期
            from datetime import datetime, timedelta

            # 计算过期阈值日期
            today = datetime.now()
            stale_threshold = (today - timedelta(days=stale_days)).strftime('%Y%m%d')

            # 获取所有已同步股票的状态
            status_map = self.data_manager.get_sync_status_for_all(freq)

            # 只保留：没同步过或数据已过期的股票
            need_sync = []
            for ts_code in ts_codes:
                status = status_map.get(ts_code)
                if status is None:
                    # 没同步过
                    need_sync.append(ts_code)
                else:
                    # 已同步，检查数据是否过期
                    end_date = status.get('end_date', '')
                    if not end_date or end_date < stale_threshold:
                        need_sync.append(ts_code)
                    # else: 数据是新的，跳过

            ts_codes = need_sync
            logger.info(f"Found {len(ts_codes)} stocks need sync (checked freshness check passed)")

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

        # 立即初始化进度（循环开始前就创建running状态记录）
        self.data_manager.sqlite_store.update_sync_progress(
            freq, 0, total, 0, 0, 'running'
        )

        try:
            for ts_code in tqdm(ts_codes, desc=f"Syncing {freq}"):
                ok, count = self.data_manager.download_and_save(ts_code, freq)
                if ok:
                    success += 1
                else:
                    failed += 1

                # 更新持久化进度
                self.data_manager.sqlite_store.update_sync_progress(
                    freq, success + failed, total, success, failed, 'running'
                )

                # 进度回调
                if progress_callback is not None:
                    progress_callback(success + failed, total, success, failed)

                if (success + failed) % 50 == 0:
                    logger.info(f"Sync progress: {success + failed}/{total}, success={success}")

            # 记录同步完成
            self.data_manager.sqlite_store.log_sync_end(
                log_id, success, failed, 'completed'
            )
            self.data_manager.sqlite_store.finish_sync_progress(freq, success, failed)
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
