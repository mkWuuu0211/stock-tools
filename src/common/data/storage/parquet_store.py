"""Parquet文件存储引擎"""
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

from config.settings import PROCESSED_DATA_DIR


class ParquetStore:
    """基于Parquet的时序数据存储

    存储结构: data/processed/{freq}/{ts_code}.parquet
    """

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or PROCESSED_DATA_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, ts_code: str, freq: str) -> Path:
        """获取文件路径"""
        freq_dir = self.base_dir / freq
        freq_dir.mkdir(exist_ok=True)
        return freq_dir / f"{ts_code}.parquet"

    def save(self, df: pd.DataFrame, ts_code: str, freq: str) -> bool:
        """保存K线数据"""
        if df is None or df.empty:
            logger.warning(f"Empty dataframe for {ts_code} {freq}, skipping save")
            return False

        try:
            file_path = self._get_file_path(ts_code, freq)
            # 确保数据排序
            if 'trade_date' in df.columns:
                df = df.sort_values('trade_date').reset_index(drop=True)
            elif 'trade_time' in df.columns:
                df = df.sort_values('trade_time').reset_index(drop=True)

            table = pa.Table.from_pandas(df)
            pq.write_table(table, file_path, compression='zstd')
            logger.debug(f"Saved {ts_code} {freq} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save {ts_code} {freq}: {e}")
            return False

    def load(self, ts_code: str, freq: str) -> Optional[pd.DataFrame]:
        """加载K线数据"""
        file_path = self._get_file_path(ts_code, freq)
        if not file_path.exists():
            return None

        try:
            df = pq.read_table(file_path).to_pandas()
            return df
        except Exception as e:
            logger.error(f"Failed to load {ts_code} {freq}: {e}")
            return None

    def delete(self, ts_code: str, freq: str) -> bool:
        """删除数据"""
        file_path = self._get_file_path(ts_code, freq)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def exists(self, ts_code: str, freq: str) -> bool:
        """检查数据是否存在"""
        file_path = self._get_file_path(ts_code, freq)
        return file_path.exists() and file_path.stat().st_size > 0

    def get_all_ts_codes(self, freq: str) -> List[str]:
        """获取该周期下所有已存储的股票代码"""
        freq_dir = self.base_dir / freq
        if not freq_dir.exists():
            return []

        ts_codes = []
        for file in freq_dir.glob("*.parquet"):
            ts_code = file.stem
            ts_codes.append(ts_code)

        return ts_codes

    def batch_save(self, data_dict: Dict[str, pd.DataFrame], freq: str) -> int:
        """批量保存数据"""
        success = 0
        for ts_code, df in data_dict.items():
            if self.save(df, ts_code, freq):
                success += 1
        logger.info(f"Batch saved {success}/{len(data_dict)} files to {freq}")
        return success
