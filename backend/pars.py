import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

class MOEXDataFetcher:
    """
    Загрузчик исторических данных с Московской биржи (MOEX ISS API).
    Поддерживает акции и валютные пары, дневные и часовые таймфреймы.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})

    def get_stock_data(self, ticker: str, board: str = 'TQBR', days: int = 365, interval: int = 24) -> pd.DataFrame:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/{board}/securities/{ticker}/candles.json"
        params = {'from': start_date, 'till': end_date, 'interval': interval}
        
        return self._fetch_and_parse(url, params, ticker, is_currency=False)

    def get_currency_data(self, ticker: str, board: str = 'CETS', days: int = 365, interval: int = 24) -> pd.DataFrame:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        url = f"https://iss.moex.com/iss/engines/currency/markets/selt/boards/{board}/securities/{ticker}/candles.json"
        params = {'from': start_date, 'till': end_date, 'interval': interval}
        
        return self._fetch_and_parse(url, params, ticker, is_currency=True)

    def _fetch_and_parse(self, url: str, params: dict, ticker: str, is_currency: bool = False) -> pd.DataFrame:
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'candles' not in data:
                return pd.DataFrame()
            
            candles_data = data['candles']
            if 'columns' not in candles_data or 'data' not in candles_data:
                return pd.DataFrame()
            
            columns = candles_data['columns']
            rows = candles_data['data']
            
            if not rows or not isinstance(rows, (list, tuple)):
                return pd.DataFrame()
            
            df = pd.DataFrame(rows, columns=columns)
            
            if 'begin' in df.columns:
                df['Date'] = pd.to_datetime(df['begin'])
                df = df.set_index('Date').sort_index()
            
            if is_currency:
                if 'volume' in df.columns:
                    df = df.drop(columns=['volume'])
            else:
                if 'value' in df.columns:
                    df = df.drop(columns=['value'])
            
            rename_map = {
                'open': 'Open', 'close': 'Close', 'high': 'High',
                'low': 'Low', 'volume': 'Volume', 'value': 'Volume'
            }
            df = df.rename(columns=rename_map)
            
            target_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            available = [c for c in target_cols if c in df.columns]
            
            for col in available:
                df[col] = df[col].replace({None: np.nan})
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            if is_currency and 'Volume' in df.columns:
                df['Volume'] = df['Volume'].fillna(0)
            
            df = df.dropna(how='all')
            return df[available]
            
        except Exception as e:
            print(f"❌ Ошибка при загрузке {ticker}: {e}")
            return pd.DataFrame()


# === ЗАПУСК ===
if __name__ == "__main__":
    fetcher = MOEXDataFetcher()
    tickers_stocks = ['SBER', 'GAZP', 'OZON']
    
    # Определяем путь к папке data (на уровень выше src/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    print("=" * 60)
    print("📅 ЗАГРУЗКА ДНЕВНЫХ СВЕЧЕЙ (1D)")
    print("=" * 60)
    
    for ticker in tickers_stocks:
        print(f"\n📈 Загружаем {ticker} (1D)...")
        df = fetcher.get_stock_data(ticker, days=365, interval=24)
        if not df.empty:
            print(f"✅ {ticker}: {len(df)} записей")
            df.to_csv(os.path.join(data_dir, f"{ticker}.csv"), index=True)
        else:
            print(f"❌ {ticker}: нет данных")
    
    print("\n" + "=" * 60)
    print("⏰ ЗАГРУЗКА ЧАСОВЫХ СВЕЧЕЙ (1H)")
    print("=" * 60)
    
    for ticker in tickers_stocks:
        print(f"\n⏰ Загружаем {ticker} (1H)...")
        df = fetcher.get_stock_data(ticker, days=30, interval=60)
        if not df.empty:
            print(f"✅ {ticker}: {len(df)} записей")
            df.to_csv(os.path.join(data_dir, f"{ticker}_1h.csv"), index=True)
        else:
            print(f"❌ {ticker}: нет данных")
      
    print("\n" + "=" * 60)
    print("🎉 ВСЕ ДАННЫЕ ЗАГРУЖЕНЫ!")
    print("=" * 60)