"""SQLite元数据存储"""
import sqlite3
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
from loguru import logger

from config.settings import SQLITE_DB_PATH


class SQLiteStore:
    """SQLite元数据存储

    存储股票基本信息、数据同步状态等
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or SQLITE_DB_PATH
        self._init_db()

    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                area TEXT,
                industry TEXT,
                list_date TEXT,
                exchange TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 数据同步状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_status (
                ts_code TEXT,
                freq TEXT,
                start_date TEXT,
                end_date TEXT,
                bars_count INTEGER,
                last_sync TIMESTAMP,
                PRIMARY KEY (ts_code, freq)
            )
        ''')

        # 同步日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                freq TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_stocks INTEGER,
                success_count INTEGER,
                failed_count INTEGER,
                status TEXT,
                error_message TEXT
            )
        ''')

        # 实时进度表 - 记录当前/最近一次同步的详细进度
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                freq TEXT,
                current INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                success INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                failed_stocks TEXT,  -- 逗号分隔的失败股票代码
                status TEXT DEFAULT 'idle',  -- idle/running/completed/failed
                last_update TIMESTAMP,
                session_id TEXT
            )
        ''')

        # 为旧数据库添加 failed_stocks 字段
        try:
            cursor.execute("ALTER TABLE sync_progress ADD COLUMN failed_stocks TEXT")
        except:
            pass  # 字段已存在，忽略

        conn.commit()
        conn.close()
        logger.debug(f"SQLiteStore initialized at {self.db_path}")

    def save_stock_list(self, df: pd.DataFrame) -> int:
        """保存股票列表，更新存在的记录"""
        conn = self._get_connection()

        insert_sql = '''
            REPLACE INTO stocks (ts_code, symbol, name, area, industry, list_date, exchange)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''

        count = 0
        for _, row in df.iterrows():
            values = (
                row.get('ts_code'),
                row.get('symbol'),
                row.get('name'),
                row.get('area', ''),
                row.get('industry', ''),
                row.get('list_date', ''),
                row.get('exchange', ''),
            )
            conn.execute(insert_sql, values)
            count += 1

        conn.commit()
        conn.close()
        logger.info(f"Saved {count} stocks to metadata")
        return count

    def get_stock_list(self) -> pd.DataFrame:
        """获取所有股票列表"""
        conn = self._get_connection()
        df = pd.read_sql("SELECT * FROM stocks", conn)
        conn.close()
        return df

    def get_stock_by_name(self, name: str) -> Optional[pd.DataFrame]:
        """根据名称搜索股票"""
        conn = self._get_connection()
        query = "SELECT * FROM stocks WHERE name LIKE ?"
        df = pd.read_sql(query, conn, params=(f"%{name}%",))
        conn.close()
        return df if not df.empty else None

    def get_stock_by_symbol(self, symbol: str) -> Optional[pd.DataFrame]:
        """根据代码搜索股票"""
        conn = self._get_connection()
        query = "SELECT * FROM stocks WHERE symbol = ? OR ts_code LIKE ?"
        df = pd.read_sql(query, conn, params=(symbol, f"{symbol}%"))
        conn.close()
        return df if not df.empty else None

    def update_sync_status(self, ts_code: str, freq: str,
                          start_date: str, end_date: str, bars_count: int):
        """更新同步状态"""
        conn = self._get_connection()
        now = datetime.now().isoformat()

        sql = '''
            REPLACE INTO sync_status (ts_code, freq, start_date, end_date, bars_count, last_sync)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        conn.execute(sql, (ts_code, freq, start_date, end_date, bars_count, now))
        conn.commit()
        conn.close()

    def get_sync_status(self, ts_code: str, freq: str) -> Optional[Dict]:
        """获取同步状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM sync_status WHERE ts_code = ? AND freq = ?"
        cursor.execute(sql, (ts_code, freq))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            'ts_code': row[0],
            'freq': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'bars_count': row[4],
            'last_sync': row[5],
        }

    def get_all_sync_status(self, freq: str) -> pd.DataFrame:
        """获取某个频率所有同步状态"""
        conn = self._get_connection()
        df = pd.read_sql("SELECT * FROM sync_status WHERE freq = ?", conn, params=(freq,))
        conn.close()
        return df

    def get_stocks_needing_update(self, freq: str, days_threshold: int = 1) -> List[str]:
        """获取需要更新的股票列表"""
        # 这里简化处理，返回所有未同步的
        # 实际应该比较最后同步时间和最新交易日
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT s.ts_code FROM stocks s
            LEFT JOIN sync_status st ON s.ts_code = st.ts_code AND st.freq = ?
            WHERE st.ts_code IS NULL OR st.last_sync < date('now', '-1 day')
        '''
        cursor.execute(sql, (freq,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def log_sync_start(self, freq: str, total_stocks: int) -> int:
        """记录同步开始"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        sql = '''
            INSERT INTO sync_log (freq, start_time, total_stocks, status)
            VALUES (?, ?, ?, 'running')
        '''
        conn.execute(sql, (freq, now, total_stocks))
        conn.commit()
        log_id = conn.cursor().lastrowid
        conn.close()
        return log_id

    def log_sync_end(self, log_id: int, success_count: int,
                     failed_count: int, status: str, error_message: str = None):
        """记录同步结束"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        sql = '''
            UPDATE sync_log
            SET end_time = ?, success_count = ?, failed_count = ?, status = ?, error_message = ?
            WHERE id = ?
        '''
        conn.execute(sql, (now, success_count, failed_count, status, error_message, log_id))
        conn.commit()

    def get_sync_status_map(self, freq: str) -> Dict[str, Dict]:
        """获取指定周期所有股票的同步状态

        Returns:
            {ts_code: {start_date, end_date, bars_count, last_sync}}
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = "SELECT ts_code, start_date, end_date, bars_count, last_sync FROM sync_status WHERE freq = ?"
        cursor.execute(sql, (freq,))
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row[0]] = {
                'ts_code': row[0],
                'start_date': row[1],
                'end_date': row[2],
                'bars_count': row[3],
                'last_sync': row[4]
            }
        return result

    # ========== 同步进度管理 ==========

    def update_sync_progress(self, freq: str, current: int, total: int, success: int, failed: int, status: str = 'running'):
        """更新同步进度"""
        conn = self._get_connection()
        now = datetime.now().isoformat()

        # 先检查是否有该周期的进行中记录
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sync_progress WHERE freq = ? AND status = 'running'", (freq,))
        existing = cursor.fetchone()

        if existing:
            sql = '''
                UPDATE sync_progress
                SET current = ?, total = ?, success = ?, failed = ?, status = ?, last_update = ?
                WHERE id = ?
            '''
            conn.execute(sql, (current, total, success, failed, status, now, existing[0]))
        else:
            sql = '''
                INSERT INTO sync_progress (freq, current, total, success, failed, status, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            conn.execute(sql, (freq, current, total, success, failed, status, now))

        conn.commit()
        conn.close()

    def finish_sync_progress(self, freq: str, success: int, failed: int, failed_stocks: List[str] = None):
        """标记同步完成"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        failed_stocks_str = ','.join(failed_stocks) if failed_stocks else ''
        sql = '''
            UPDATE sync_progress
            SET current = total, success = ?, failed = ?, failed_stocks = ?, status = 'completed', last_update = ?
            WHERE freq = ? AND status = 'running'
        '''
        conn.execute(sql, (success, failed, failed_stocks_str, now, freq))
        conn.commit()
        conn.close()

    def get_failed_stocks(self, freq: str) -> List[str]:
        """获取最近一次同步失败的股票列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT failed_stocks FROM sync_progress
            WHERE freq = ? AND failed_stocks IS NOT NULL AND failed_stocks != ''
            ORDER BY last_update DESC LIMIT 1
        ''', (freq,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0].split(',')
        return []

    def cancel_sync_progress(self, freq: str):
        """取消正在进行的同步（标记为失败）"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        sql = '''
            UPDATE sync_progress
            SET status = 'failed', last_update = ?
            WHERE freq = ? AND status = 'running'
        '''
        conn.execute(sql, (now, freq))
        conn.commit()
        conn.close()

    def cancel_all_sync_progress(self):
        """取消所有正在进行的同步"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        sql = '''
            UPDATE sync_progress
            SET status = 'failed', last_update = ?
            WHERE status = 'running'
        '''
        conn.execute(sql, (now,))
        conn.commit()
        conn.close()

    def get_latest_sync_progress(self, freq: str = None) -> Optional[Dict]:
        """获取最近的同步进度"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if freq:
            cursor.execute('''
                SELECT freq, current, total, success, failed, status, last_update
                FROM sync_progress
                WHERE freq = ?
                ORDER BY last_update DESC
                LIMIT 1
            ''', (freq,))
        else:
            cursor.execute('''
                SELECT freq, current, total, success, failed, status, last_update
                FROM sync_progress
                ORDER BY last_update DESC
                LIMIT 1
            ''')

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'freq': row[0],
                'current': row[1],
                'total': row[2],
                'success': row[3],
                'failed': row[4],
                'status': row[5],
                'last_update': row[6]
            }
        return None

    def _ensure_sync_progress_table(self, conn):
        """确保 sync_progress 表存在（兼容旧数据库）"""
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM sync_progress LIMIT 1")
            return True
        except:
            # 表不存在，创建它
            logger.info("sync_progress table not found, creating...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    freq TEXT,
                    current INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'idle',
                    last_update TIMESTAMP,
                    session_id TEXT
                )
            ''')
            conn.commit()
            return True

    def get_all_running_syncs(self) -> List[Dict]:
        """获取所有正在进行中的同步"""
        conn = self._get_connection()
        try:
            self._ensure_sync_progress_table(conn)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT freq, current, total, success, failed, status, last_update
                FROM sync_progress
                WHERE status = 'running'
                ORDER BY last_update DESC
            ''')
            rows = cursor.fetchall()
            conn.close()

            return [{
                'freq': row[0],
                'current': row[1],
                'total': row[2],
                'success': row[3],
                'failed': row[4],
                'status': row[5],
                'last_update': row[6]
            } for row in rows]
        except Exception as e:
            logger.warning(f"get_all_running_syncs failed: {e}")
            conn.close()
            return []

    def get_recent_sync_history(self, limit: int = 10) -> List[Dict]:
        """获取最近的同步历史"""
        conn = self._get_connection()
        try:
            self._ensure_sync_progress_table(conn)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT freq, current, total, success, failed, status, last_update
                FROM sync_progress
                ORDER BY last_update DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()

            return [{
                'freq': row[0],
                'current': row[1],
                'total': row[2],
                'success': row[3],
                'failed': row[4],
                'status': row[5],
                'last_update': row[6]
            } for row in rows]
        except Exception as e:
            logger.warning(f"get_recent_sync_history failed: {e}")
            conn.close()
            return []
