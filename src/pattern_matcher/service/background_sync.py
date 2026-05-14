"""后台同步服务

同步在独立进程中运行，避免Streamlit页面刷新中断同步
"""
import multiprocessing
import time
from typing import Optional, List, Dict
from loguru import logger

from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService


class BackgroundSyncManager:
    """后台同步管理器"""

    def __init__(self):
        self._active_processes: Dict[str, multiprocessing.Process] = {}

    @staticmethod
    def _sync_worker_process(
        freq: str,
        skip_existing: bool = True,
        limit: int = None,
        specific_stocks: List[str] = None,
    ):
        """同步工作进程（在独立进程中运行）

        注意：这个函数必须是顶层函数，不能是实例方法
        否则multiprocessing无法pickle序列化

        Args:
            specific_stocks: 只同步指定股票列表（用于重试失败股票）
        """
        try:
            # 在子进程中重新初始化服务（避免跨进程共享数据库连接）
            dm = DataManager()
            sync_service = SyncService(dm)

            if specific_stocks:
                # 重试指定股票
                logger.info(f"Retrying {len(specific_stocks)} failed stocks for {freq}")
                success, failed = sync_service.sync_specific_stocks(freq, specific_stocks)
            else:
                success, failed = sync_service.sync_freq(
                    freq=freq,
                    skip_existing=skip_existing,
                    limit=limit,
                    progress_callback=None,  # 进度通过SQLite持久化，不需要回调
                )

            logger.info(f"Background sync completed for {freq}: success={success}, failed={failed}")
            return success, failed

        except Exception as e:
            logger.exception(f"Background sync failed for {freq}: {e}")
            # 标记同步失败
            try:
                dm.sqlite_store.finish_sync_progress(freq, 0, 0)
            except:
                pass
            return 0, 0

    def start_sync(
        self,
        freq: str,
        skip_existing: bool = True,
        limit: int = None,
    ) -> bool:
        """启动后台同步

        Args:
            freq: 同步周期
            skip_existing: 是否跳过期数据
            limit: 限制数量

        Returns:
            是否成功启动
        """
        # 检查该周期是否已有在运行的同步
        if self.is_sync_running(freq):
            logger.warning(f"Sync already running for {freq}")
            return False

        # 启动新进程
        process = multiprocessing.Process(
            target=self._sync_worker_process,
            args=(freq, skip_existing, limit),
            daemon=True,
        )
        process.start()

        self._active_processes[freq] = process
        logger.info(f"Started background sync for {freq}, PID={process.pid}")
        return True

    def start_multiple_syncs(
        self,
        freqs: List[str],
        skip_existing: bool = True,
        limit: int = None,
    ) -> List[str]:
        """启动多个后台同步

        Returns:
            成功启动的周期列表
        """
        started = []
        for freq in freqs:
            if self.start_sync(freq, skip_existing, limit):
                started.append(freq)
                # 稍微延迟，避免同时初始化太多连接
                time.sleep(0.5)
        return started

    def retry_failed_stocks(self, freq: str) -> bool:
        """重试该周期最近一次同步失败的股票

        Returns:
            是否成功启动重试
        """
        # 检查是否已有同步在运行
        if self.is_sync_running(freq):
            logger.warning(f"Sync already running for {freq}")
            return False

        # 获取失败股票列表
        dm = DataManager()
        failed_stocks = dm.sqlite_store.get_failed_stocks(freq)

        if not failed_stocks:
            logger.info(f"No failed stocks found for {freq}")
            return False

        # 启动后台重试
        process = multiprocessing.Process(
            target=self._sync_worker_process,
            args=(freq, False, None, failed_stocks),
            daemon=True,
        )
        process.start()

        self._active_processes[freq] = process
        logger.info(f"Started retry sync for {freq}, {len(failed_stocks)} stocks, PID={process.pid}")
        return True

    def is_sync_running(self, freq: str) -> bool:
        """检查某个周期是否正在同步"""
        # 先检查进程列表
        if freq in self._active_processes:
            if self._active_processes[freq].is_alive():
                return True
            else:
                # 进程已结束，清理
                del self._active_processes[freq]

        # 再检查数据库状态（应对服务重启后的情况）
        dm = DataManager()
        running_syncs = dm.sqlite_store.get_all_running_syncs()
        return any(s['freq'] == freq for s in running_syncs)

    def get_running_syncs(self) -> List[str]:
        """获取所有正在运行的同步周期"""
        # 清理已结束的进程
        finished = [freq for freq, proc in self._active_processes.items() if not proc.is_alive()]
        for freq in finished:
            del self._active_processes[freq]

        # 返回正在运行的
        return list(self._active_processes.keys())

    def wait_for_all(self, timeout: int = None):
        """等待所有同步完成"""
        for freq, proc in list(self._active_processes.items()):
            proc.join(timeout=timeout)
            if not proc.is_alive():
                del self._active_processes[freq]


# 全局单例
_sync_manager: Optional[BackgroundSyncManager] = None


def get_background_sync_manager() -> BackgroundSyncManager:
    """获取后台同步管理器单例"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = BackgroundSyncManager()
    return _sync_manager
