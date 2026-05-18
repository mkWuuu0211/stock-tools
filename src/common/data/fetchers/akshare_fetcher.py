"""AkShare数据源适配器"""
import pandas as pd
import akshare as ak
import time
from typing import List, Optional, Dict
from loguru import logger


class AKShareFetcher:
    """AkShare数据获取器，完全免费无需token"""

    def get_stock_list(self) -> pd.DataFrame:
        """获取沪深股票列表"""
        logger.info("Fetching stock list from AkShare")
        df = ak.stock_info_a_code_name()
        # AkShare 返回格式: code, name
        df.rename(columns={'code': 'symbol', 'name': 'name'}, inplace=True)
        # 添加ts_code格式
        df['ts_code'] = df['symbol'].apply(lambda x: f"{x}.SH" if x.startswith('6') or x.startswith('9') else f"{x}.SZ")
        logger.info(f"Got {len(df)} stocks from AkShare")
        return df

    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None, retries: int = 1) -> pd.DataFrame:
        """获取日线K线数据

        symbol: 纯数字代码，如 "000001"
        retries: 重试次数
        """
        logger.debug(f"Fetching daily bars for {symbol} from AkShare")

        for attempt in range(retries):
            try:
                # AkShare获取历史数据
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                if df is None or df.empty:
                    time.sleep(0.5)
                    continue

                # 重命名列名以保持一致
                column_map = {
                    '日期': 'trade_date',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '涨跌幅': 'pct_chg',
                }
                df.rename(columns=column_map, inplace=True)

                # 格式化日期
                df['trade_date'] = df['trade_date'].astype(str).str.replace('-', '')

                df = df.sort_values('trade_date')
                time.sleep(0.3)  # 避免请求太频繁
                return df

            except Exception as e:
                logger.warning(f"AkShare fetch attempt {attempt+1} failed for {symbol}: {e}")
                time.sleep(0.1)  # 快速重试，AkShare常被封，尽快跳Baostock

        logger.error(f"AkShare fetch failed after {retries} attempts for {symbol}")
        return pd.DataFrame()

    def get_minute_bars(self, symbol: str, freq: str = "15min") -> pd.DataFrame:
        """获取分钟线数据

        symbol: 纯数字代码
        freq: 1min, 5min, 15min, 30min, 60min
        """
        ak_freq_map = {
            "1min": "1",
            "5min": "5",
            "15min": "15",
            "30min": "30",
            "60min": "60",
        }
        ak_freq = ak_freq_map.get(freq, "15")

        logger.debug(f"Fetching {freq} bars for {symbol} from AkShare")

        try:
            df = ak.stock_zh_a_minute(symbol=symbol, period=ak_freq)
            if df is None or df.empty:
                return pd.DataFrame()

            column_map = {
                'day': 'trade_date',
                'time': 'trade_time',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
            }
            df.rename(columns=column_map, inplace=True)
            return df

        except Exception as e:
            logger.error(f"AkShare minute fetch failed for {symbol} {freq}: {e}")
            return pd.DataFrame()

    def batch_download_daily(self, symbols: List[str], start_date: str = None, end_date: str = None) -> Dict[str, pd.DataFrame]:
        """批量下载日线数据"""
        results = {}
        total = len(symbols)

        for i, symbol in enumerate(symbols):
            try:
                df = self.get_daily_bars(symbol, start_date, end_date)
                if not df.empty:
                    results[symbol] = df
                if (i + 1) % 50 == 0:
                    logger.info(f"Downloaded {i + 1}/{total}")
            except Exception as e:
                logger.error(f"Failed to download {symbol}: {e}")

        logger.info(f"Completed batch download: {len(results)}/{total} successful")
        return results
