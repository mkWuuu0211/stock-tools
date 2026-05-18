"""Tushare数据源适配器"""
import pandas as pd
import tushare as ts
from typing import List, Optional, Dict
from loguru import logger

from config.settings import TUSHARE_TOKEN


class TushareFetcher:
    """Tushare数据获取器"""

    def __init__(self, token: str = None):
        self.token = token or TUSHARE_TOKEN
        if not self.token:
            logger.warning("Tushare token not set, some functions may not work")
        else:
            ts.set_token(self.token)
            self.pro = ts.pro_api()

    def get_stock_list(self) -> pd.DataFrame:
        """获取沪深股票列表"""
        if not self.token:
            raise ValueError("Tushare token required for getting stock list")

        logger.info("Fetching stock list from Tushare")
        df = self.pro.stock_basic(exchange='', list_status='L',
                                   fields='ts_code,symbol,name,area,industry,list_date,exchange')
        logger.info(f"Got {len(df)} stocks from Tushare")
        return df

    def get_daily_bars(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取日线K线数据"""
        if not self.token:
            # 使用旧接口作为备选
            logger.debug(f"Using public interface for {ts_code}")
            code = ts_code.split('.')[0]
            df = ts.get_hist_data(code, start=start_date, end=end_date)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.sort_index()
            df = df.reset_index()
            df.rename(columns={'date': 'trade_date', 'open': 'open', 'high': 'high',
                             'low': 'low', 'close': 'close', 'volume': 'volume'},
                      inplace=True)
            return df

        logger.debug(f"Fetching daily bars for {ts_code}")
        df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.sort_values('trade_date')
        return df

    def get_minute_bars(self, ts_code: str, freq: str = "15min") -> pd.DataFrame:
        """获取分钟线数据

        freq: 1min, 5min, 15min, 30min, 60min
        """
        if not self.token:
            raise ValueError("Tushare token required for minute data")

        # Tushare 的分钟线接口
        freq_map = {
            "1min": "1min",
            "5min": "5min",
            "15min": "15min",
            "30min": "30min",
            "60min": "60min",
        }
        tushare_freq = freq_map.get(freq, freq)

        logger.debug(f"Fetching {freq} bars for {ts_code}")
        df = self.pro.bar(ts_code=ts_code, freq=tushare_freq)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.sort_values('trade_time')
        return df

    def get_all_calendars(self) -> pd.DataFrame:
        """获取交易日历"""
        if not self.token:
            return pd.DataFrame()

        df = self.pro.trade_cal(exchange='', start_date='19900101')
        return df

    def batch_download_daily(self, ts_codes: List[str], start_date: str = None, end_date: str = None) -> Dict[str, pd.DataFrame]:
        """批量下载日线数据"""
        results = {}
        total = len(ts_codes)

        for i, ts_code in enumerate(ts_codes):
            try:
                df = self.get_daily_bars(ts_code, start_date, end_date)
                if not df.empty:
                    results[ts_code] = df
                if (i + 1) % 100 == 0:
                    logger.info(f"Downloaded {i + 1}/{total}")
            except Exception as e:
                logger.error(f"Failed to download {ts_code}: {e}")

        logger.info(f"Completed batch download: {len(results)}/{total} successful")
        return results
