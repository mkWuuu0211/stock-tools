"""Baostock数据源适配器 - 免费日线数据"""
import pandas as pd
import baostock as bs
from typing import List, Optional, Dict
from loguru import logger


class BaoStockFetcher:
    """Baostock数据获取器，完全免费无需token"""

    def __init__(self):
        self.login()

    def login(self):
        """登录baostock"""
        try:
            lg = bs.login()
            if lg.error_code != '0':
                logger.warning(f"Baostock login failed: {lg.error_msg}")
            else:
                logger.debug("Baostock logged in")
        except Exception as e:
            logger.error(f"Baostock init failed: {e}")

    def __del__(self):
        """析构时登出"""
        try:
            bs.logout()
        except:
            pass

    def get_stock_list(self) -> pd.DataFrame:
        """获取沪深股票列表"""
        logger.info("Fetching stock list from Baostock")

        rs = bs.query_stock_basic()
        data_list = []
        while (rs.next()):
            data_list.append(rs.get_row_data())
        df = pd.DataFrame(data_list, columns=rs.fields)

        # 筛选出上市的A股 - type='1'是股票, status='1'是上市状态
        df = df[(df['type'] == '1') & (df['status'] == '1')]
        df = df[['code', 'code_name', 'ipoDate']].copy()

        # 转换代码格式
        # baostock code格式: sh.600000 -> 转换为 600000.SH
        def convert_code(code):
            exchange, symbol = code.split('.')
            if exchange == 'sh':
                return f"{symbol}.SH"
            else:
                return f"{symbol}.SZ"

        df['ts_code'] = df['code'].apply(convert_code)
        df.rename(columns={'code': 'symbol', 'code_name': 'name', 'ipoDate': 'list_date'}, inplace=True)

        df['symbol'] = df['symbol'].apply(lambda x: x.split('.')[1])

        # 修复Baostock中文乱码问题
        # Baostock返回GBK编码的字符串被错误解码为UTF-8
        # 需要先编码为UTF-8字节，再用GBK解码
        def fix_encoding(s):
            if isinstance(s, str):
                try:
                    return s.encode('utf-8').decode('gbk')
                except:
                    try:
                        # 备用方案：如果UTF-8不行，尝试latin1
                        return s.encode('latin1').decode('gbk')
                    except:
                        return s
            return s

        df['name'] = df['name'].apply(fix_encoding)

        logger.info(f"Got {len(df)} stocks from Baostock")
        return df

    def get_daily_bars(self, symbol: str, start_date: str = '1990-01-01', end_date: str = '') -> pd.DataFrame:
        """获取日线K线数据

        symbol: ts_code格式，如 "000001.SZ"
        """
        # 转换为baostock格式
        if '.' in symbol:
            code_parts = symbol.split('.')
            pure_code = code_parts[0]
            exchange = code_parts[1].lower()
            bs_code = f"{exchange}.{pure_code}"
        else:
            if symbol.startswith('6'):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"

        logger.debug(f"Fetching daily bars for {symbol} from Baostock")

        try:
            # 获取日线数据
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"  # 前复权
            )

            data_list = []
            while (rs.next()):
                data_list.append(rs.get_row_data())
            df = pd.DataFrame(data_list, columns=rs.fields)

            if df is None or df.empty:
                return pd.DataFrame()

            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                df[col] = pd.to_numeric(df[col])

            # 重命名列名以保持一致
            df.rename(columns={'date': 'trade_date'}, inplace=True)

            # 格式化日期
            df['trade_date'] = df['trade_date'].astype(str).str.replace('-', '')

            df = df.sort_values('trade_date')

            return df

        except Exception as e:
            logger.error(f"Baostock fetch failed for {symbol}: {e}")
            return pd.DataFrame()
