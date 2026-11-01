import sqlite3
import pandas as pd
from datetime import datetime
import os
import threading

class TradingDatabase:
    """
    База данных для хранения исторических свечей, сделок и результатов.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(project_root, 'trading_data.db')
        
        self.db_path = db_path
        self.lock = threading.Lock()
        self._create_tables()
    
    def _get_conn(self):
        """Создаём НОВОЕ соединение для каждого запроса (решает проблему курсоров)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_tables(self):
        """Создаём таблицы если их нет."""
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS candles (
                        ticker TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        date TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        PRIMARY KEY (ticker, timeframe, date)
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        action TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        strategy TEXT,
                        confidence REAL,
                        profit REAL,
                        status TEXT DEFAULT 'OPEN'
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS model_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        train_date TEXT NOT NULL,
                        accuracy REAL,
                        total_trades INTEGER,
                        win_rate REAL,
                        model_version TEXT
                    )
                ''')
                conn.commit()
            finally:
                conn.close()
    
    def save_candles(self, ticker: str, timeframe: str, df: pd.DataFrame):
        """Сохраняем свечи в базу."""
        print(f" Сохраняем {len(df)} свечей {ticker} ({timeframe}) в БД...")
        with self.lock:
            conn = self._get_conn()
            try:
                for date, row in df.iterrows():
                    conn.execute('''
                        INSERT OR REPLACE INTO candles 
                        (ticker, timeframe, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ticker, timeframe,
                        date.strftime('%Y-%m-%d %H:%M:%S'),
                        row['Open'], row['High'], row['Low'], row['Close'], row['Volume']
                    ))
                conn.commit()
                print(f"✅ Сохранено")
            finally:
                conn.close()
    
    def load_candles(self, ticker: str, timeframe: str, days: int = 365) -> pd.DataFrame:
        """Загружаем свечи из базы."""
        with self.lock:
            conn = self._get_conn()
            try:
                query = f'''
                    SELECT date, open, high, low, close, volume
                    FROM candles
                    WHERE ticker = ? AND timeframe = ?
                      AND date >= datetime('now', '-{days} days')
                    ORDER BY date ASC
                '''
                df = pd.read_sql_query(query, conn, params=(ticker, timeframe))
                
                if df.empty:
                    return pd.DataFrame()
                
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low', 
                    'close': 'Close', 'volume': 'Volume'
                })
                return df
            finally:
                conn.close()
    
    def save_trade(self, ticker: str, action: str, price: float, 
                   quantity: int, strategy: str, confidence: float):
        """Записываем сделку в базу."""
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute('''
                    INSERT INTO trades (ticker, action, price, quantity, date, strategy, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticker, action, price, quantity,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    strategy, confidence
                ))
                conn.commit()
                print(f"📝 Сделка записана: {action} {quantity} {ticker} @ {price:.2f}₽")
            finally:
                conn.close()
    
    def get_open_trades(self, ticker: str = None) -> pd.DataFrame:
        """Получаем все открытые сделки."""
        with self.lock:
            conn = self._get_conn()
            try:
                if ticker:
                    query = "SELECT * FROM trades WHERE status = 'OPEN' AND ticker = ?"
                    params = (ticker,)
                else:
                    query = "SELECT * FROM trades WHERE status = 'OPEN'"
                    params = None
                
                return pd.read_sql_query(query, conn, params=params)
            finally:
                conn.close()
    
    def close_trade(self, trade_id: int, current_price: float):
        """Закрываем сделку и считаем прибыль."""
        with self.lock:
            conn = self._get_conn()
            try:
                trade = pd.read_sql_query(
                    "SELECT * FROM trades WHERE id = ?", 
                    conn, params=(trade_id,)
                ).iloc[0]
                
                if trade['action'] == 'BUY':
                    profit = (current_price - trade['price']) * trade['quantity']
                else:
                    profit = (trade['price'] - current_price) * trade['quantity']
                
                conn.execute('''
                    UPDATE trades 
                    SET status = 'CLOSED', profit = ?
                    WHERE id = ?
                ''', (profit, trade_id))
                conn.commit()
                
                print(f"✅ Сделка #{trade_id} закрыта. Прибыль: {profit:.2f}₽")
                return profit
            finally:
                conn.close()
    
    def get_trade_stats(self) -> dict:
        """Статистика по всем закрытым сделкам."""
        with self.lock:
            conn = self._get_conn()
            try:
                stats = pd.read_sql_query('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                        AVG(profit) as avg_profit,
                        SUM(profit) as total_profit
                    FROM trades 
                    WHERE status = 'CLOSED'
                ''', conn).iloc[0]
                
                win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
                
                return {
                    'total_trades': int(stats['total']) if pd.notna(stats['total']) else 0,
                    'wins': int(stats['wins']) if pd.notna(stats['wins']) else 0,
                    'win_rate': float(win_rate),
                    'avg_profit': float(stats['avg_profit']) if pd.notna(stats['avg_profit']) else 0,
                    'total_profit': float(stats['total_profit']) if pd.notna(stats['total_profit']) else 0
                }
            finally:
                conn.close()