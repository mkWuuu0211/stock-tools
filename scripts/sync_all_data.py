#!/usr/bin/env python3
"""全量数据同步脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from loguru import logger

from src.common.data.data_manager import DataManager
from src.pattern_matcher.service.sync_service import SyncService
from config.settings import SUPPORTED_FREQS


@click.command()
@click.option('--freqs', '-f', default='D', help=f'Comma separated frequencies to sync. Supported: {",".join(SUPPORTED_FREQS.keys())}')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of stocks to sync (for testing)')
@click.option('--force/--no-force', default=False, help='Force resync all stocks even if already synced')
def main(freqs, limit, force):
    """全量同步指定周期的股票数据"""
    logger.info("Starting full sync...")

    # 解析频率列表
    freq_list = [f.strip() for f in freqs.split(',') if f.strip()]

    # 验证
    for f in freq_list:
        if f not in SUPPORTED_FREQS:
            logger.error(f"Unsupported frequency: {f}")
            logger.info(f"Supported frequencies: {list(SUPPORTED_FREQS.keys())}")
            sys.exit(1)

    # 初始化服务
    dm = DataManager()
    service = SyncService(dm)

    # 先同步股票列表
    logger.info("Syncing stock list...")
    count = service.sync_stock_list(force_update=True)
    logger.info(f"Stock list done: {count} stocks")

    # 同步数据
    results = service.sync_multiple_freqs(
        freq_list,
        skip_existing=not force,
        limit=limit
    )

    # 输出结果
    print("\n" + "=" * 50)
    print("Sync Summary:")
    print("=" * 50)

    total_success = 0
    total_failed = 0
    for freq, (success, failed) in results.items():
        print(f"  {freq:>6} : {success:>4} success, {failed:>4} failed")
        total_success += success
        total_failed += failed

    print("-" * 50)
    print(f"  Total: {total_success:>4} success, {total_failed:>4} failed")
    print("=" * 50)

    if total_failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
