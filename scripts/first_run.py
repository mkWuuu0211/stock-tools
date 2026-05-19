#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""首次运行初始化脚本

新机器克隆项目后，运行此脚本完成：
1. 检查并创建必要的数据目录
2. 从Baostock获取股票列表（无需Token）
3. 初始化SQLite数据库
4. 验证所有模块可正常导入
"""
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_directories():
    """检查并创建必要的目录"""
    print("[*] 检查数据目录...")

    dirs = [
        project_root / "data",
        project_root / "data" / "raw",
        project_root / "data" / "processed",
        project_root / "data" / "cache",
    ]

    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            print(f"  [OK] 创建目录: {d}")
        else:
            print(f"  [OK] 已存在: {d}")

    return True


def check_dependencies():
    """检查依赖是否安装"""
    print("\n[*] 检查依赖安装...")

    required = [
        "pandas",
        "numpy",
        "streamlit",
        "plotly",
        "baostock",
        "pyarrow",
        "loguru",
    ]

    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [FAIL] {pkg} (未安装)")
            missing.append(pkg)

    if missing:
        print(f"\n[WARN] 缺少依赖: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False

    return True


def init_stock_list():
    """初始化股票列表"""
    print("\n[*] 初始化股票列表...")

    from src.common.data.data_manager import DataManager

    dm = DataManager()

    # 检查是否已有股票
    existing = dm.get_stock_list()
    if len(existing) > 0:
        print(f"  [OK] 已存在 {len(existing)} 只股票数据，跳过")
        return True

    print("  从Baostock获取股票列表...")
    df = dm.get_stock_list(force_update=True)

    if df.empty:
        print("  [FAIL] 获取失败，股票列表为空")
        return False

    print(f"  [OK] 成功获取 {len(df)} 只股票")
    print(f"    - 沪市: {len(df[df['ts_code'].str.endswith('.SH')])} 只")
    print(f"    - 深市: {len(df[df['ts_code'].str.endswith('.SZ')])} 只")

    return True


def test_modules():
    """测试核心模块导入"""
    print("\n[*] 测试核心模块...")

    modules = [
        "src.common.data.storage.sqlite_store",
        "src.common.data.storage.parquet_store",
        "src.common.data.fetchers.baostock_fetcher",
        "src.pattern_matcher.algorithm.similarity",
        "src.pattern_matcher.algorithm.matcher",
        "src.pattern_matcher.service.sync_service",
    ]

    for mod in modules:
        try:
            __import__(mod)
            print(f"  [OK] {mod.split('.')[-1]}")
        except Exception as e:
            print(f"  [FAIL] {mod}: {e}")
            return False

    return True


def main():
    print("=" * 60)
    print("[*] Stock-Tools 首次运行初始化")
    print("=" * 60)

    checks = [
        ("目录结构", check_directories),
        ("依赖安装", check_dependencies),
        ("模块导入", test_modules),
        ("股票列表", init_stock_list),
    ]

    all_passed = True
    for name, check_func in checks:
        if not check_func():
            print(f"\n[!] {name} 检查失败！")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] 所有检查通过！")
        print("\n下一步:")
        print("  1. 同步日线数据: 进入「数据管理」点击「开始同步」")
        print("  2. 启动Web: streamlit run web/app.py")
        print("  3. 打开浏览器: http://localhost:8501")
    else:
        print("[FAIL] 部分检查未通过，请根据上面的提示修复后重试")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
