#!/usr/bin/env python3
"""每日数据更新脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService


def main():
    """每日更新"""
    logger.info("Starting daily update...")

    dm = DataManager()
    service = SyncService(dm)

    # 更新股票列表（如果有新股上市）
    service.sync_stock_list(force_update=False)

    # 增量更新日线数据
    success, failed = service.update_daily()

    print("\n" + "=" * 50)
    print("Daily Update Summary:")
    print("=" * 50)
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print("=" * 50)

    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
