#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从GitHub Release一键下载预置K线数据

新用户运行此脚本，一键下载样本数据
无需等待30分钟同步，1分钟内即可体验完整功能
"""
import io
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ 请先安装 requests: pip install requests")
    exit(1)


# Release下载地址（发布后更新此地址）
RELEASE_DOWNLOAD_URL = "https://github.com/mkWuuu0211/stock-tools/releases/download/v1.0.0/sample_data.zip"


def download_and_extract():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'

    print("=" * 60)
    print("🚀 下载预置K线数据包")
    print("=" * 60)
    print(f"下载地址: {RELEASE_DOWNLOAD_URL}")
    print(f"解压目录: {data_dir}")
    print()

    # 检查是否已有数据
    processed_dir = data_dir / 'processed'
    if processed_dir.exists() and any(processed_dir.rglob('*.parquet')):
        print("⚠️  检测到已有数据")
        answer = input("是否覆盖下载？(y/N): ").strip().lower()
        if answer != 'y':
            print("已取消下载")
            return

    print("正在下载... (约 250MB，请耐心等待)")
    print()

    try:
        # 下载并显示进度
        response = requests.get(RELEASE_DOWNLOAD_URL, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        zip_buffer = io.BytesIO()
        for chunk in response.iter_content(chunk_size=block_size):
            zip_buffer.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = downloaded / total_size * 100
                print(f"\r  进度: {percent:.1f}% ({downloaded/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB)", end='')

        print()
        print()
        print("正在解压...")

        # 解压
        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer) as zf:
            # 解压到项目根目录
            zf.extractall(project_root)

        # 统计解压的文件
        parquet_count = len(list(data_dir.rglob('*.parquet')))

        print()
        print("=" * 60)
        print(f"✅ 下载完成！")
        print(f"已解压到: {data_dir}")
        print(f"包含K线数据: {parquet_count} 只股票")
        print()
        print("现在可以直接启动:")
        print("  streamlit run web/app.py")
        print("=" * 60)

    except requests.exceptions.RequestException as e:
        print()
        print(f"❌ 下载失败: {e}")
        print()
        print("手动下载方式:")
        print(f"  1. 访问 {RELEASE_DOWNLOAD_URL}")
        print(f"  2. 解压到项目根目录")
    except Exception as e:
        print(f"❌ 出错: {e}")


if __name__ == '__main__':
    download_and_extract()
