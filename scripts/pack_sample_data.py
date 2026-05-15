#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包本地K线数据用于Release上传

运行此脚本将已同步的K线数据打包成 sample_data.zip
用于上传到GitHub Release，方便新用户快速开始
"""
import zipfile
from pathlib import Path
from datetime import datetime


def pack_data():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    processed_dir = data_dir / 'processed'
    output_zip = project_root / 'sample_data.zip'

    if not processed_dir.exists():
        print("❌ 没有找到processed目录，请先同步数据")
        return

    # 统计文件
    parquet_files = list(processed_dir.rglob('*.parquet'))
    total_size = sum(f.stat().st_size for f in parquet_files)

    print("=" * 60)
    print("📦 打包K线数据用于GitHub Release")
    print("=" * 60)
    print(f"数据目录: {processed_dir}")
    print(f"文件数量: {len(parquet_files)} 个")
    print(f"总大小: {total_size / 1024 / 1024:.1f} MB")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("正在压缩中...")

    # 打包文件，保持目录结构
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. 元数据数据库
        db_file = data_dir / 'stock_metadata.db'
        if db_file.exists():
            zf.write(db_file, 'data/stock_metadata.db')
            print(f"  ✓ 添加: data/stock_metadata.db")

        # 2. 所有Parquet K线数据
        for parquet_file in parquet_files:
            # 保持 data/processed/D/XXX.parquet 结构
            arcname = 'data/processed/' + str(parquet_file.relative_to(processed_dir))
            zf.write(parquet_file, arcname)

        # 3. 添加说明文件
        readme_content = f"""Stock-Tools 预置数据包
========================

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
股票数量: {len(parquet_files)} 只
数据周期: 日线(D)

使用方法:
1. 将此压缩包解压到项目根目录
2. 自动覆盖 data/ 文件夹
3. 直接启动 streamlit run web/app.py

注意:
- 此数据包只包含部分股票的样本数据
- 需要全部数据请在Web界面点击「开始同步」
"""
        zf.writestr('data/README_SAMPLE_DATA.txt', readme_content)

    final_size = output_zip.stat().st_size
    print()
    print("=" * 60)
    print(f"✅ 打包完成！")
    print(f"输出文件: {output_zip}")
    print(f"压缩后大小: {final_size / 1024 / 1024:.1f} MB")
    print()
    print("下一步:")
    print("  1. 访问 https://github.com/mkWuuu0211/stock-tools/releases")
    print("  2. 点击 'Draft a new release'")
    print("  3. 上传 sample_data.zip")
    print("  4. 填写版本号（如 v1.0.0）并发布")
    print("=" * 60)


if __name__ == '__main__':
    pack_data()
