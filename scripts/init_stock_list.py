#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化股票列表数据

新用户首次使用时运行此脚本，生成完整的股票列表元数据
无需Tushare Token，使用免费的Baostock数据源
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.common.data.data_manager import DataManager


def init_stock_list(force_update: bool = True) -> int:
    """初始化股票列表

    Args:
        force_update: 是否强制更新

    Returns:
        股票数量
    """
    logger.info("=" * 60)
    logger.info("开始初始化股票列表...")
    logger.info("数据源: Baostock (免费，无需Token)")
    logger.info("=" * 60)

    try:
        dm = DataManager()
        df = dm.get_stock_list(force_update=force_update)

        logger.success(f"✓ 成功获取 {len(df)} 只股票")
        logger.info(f"  - 沪市: {len(df[df['ts_code'].str.endswith('.SH')])} 只")
        logger.info(f"  - 深市: {len(df[df['ts_code'].str.endswith('.SZ')])} 只")

        # 显示样例
        logger.info("\n股票列表样例:")
        for _, row in df.head(5).iterrows():
            logger.info(f"  {row['ts_code']:10s} {row['name']}")

        logger.info("\n" + "=" * 60)
        logger.success("✓ 股票列表初始化完成！")
        logger.info("现在可以开始同步K线数据了")
        logger.info("=" * 60)

        return len(df)

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        logger.info("\n提示: 请检查网络连接，或稍后重试")
        return 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='初始化股票列表')
    parser.add_argument('--force', action='store_true', default=True,
                        help='强制更新股票列表')
    args = parser.parse_args()

    init_stock_list(force_update=args.force)
