import pandas as pd
import os
from pars import MOEXDataFetcher
from database import TradingDatabase

class DataPipeline:
    """
    Пайплайн загрузки и обновления данных.
    Гибрид: история из БД + свежие данные с MOEX.
    """
    
    def __init__(self, db: TradingDatabase, fetcher: MOEXDataFetcher):
        self.db = db
        self.fetcher = fetcher
    
    def update_data(self, ticker: str, timeframe: str = '1h', days: int = 365):
        print(f"\n{'='*60}")
        print(f"🔄 ОБНОВЛЕНИЕ ДАННЫХ: {ticker} ({timeframe})")
        print(f"{'='*60}")
        
        print("\n📥 Загружаем историю из базы данных...")
        db_data = self.db.load_candles(ticker, timeframe, days=days)
        print(f"   В базе: {len(db_data)} свечей")
        
        last_db_date = db_data.index[-1] if not db_data.empty else None
        
        fetch_days = 30 if timeframe == '1h' else days
        interval = 60 if timeframe == '1h' else 24
        
        print(f"\n🌐 Скачиваем свежие данные с MOEX (последние {fetch_days} дней)...")
        fresh_data = self.fetcher.get_stock_data(ticker, days=fetch_days, interval=interval)
        print(f"   Скачано: {len(fresh_data)} свечей")
        
        if fresh_data.empty:
            print("❌ Не удалось скачать данные с MOEX")
            return db_data if not db_data.empty else pd.DataFrame()
        
        print("\n🔗 Объединяем данные...")
        if not db_data.empty:
            fresh_data = fresh_data[fresh_data.index > last_db_date]
            combined = pd.concat([db_data, fresh_data])
        else:
            combined = fresh_data
        
        combined = combined.sort_index()
        combined = combined[~combined.index.duplicated(keep='last')]
        
        print(f"   Итого: {len(combined)} уникальных свечей")
        
        print("\n💾 Сохраняем в базу данных...")
        self.db.save_candles(ticker, timeframe, combined)
        
        return combined
    
    def get_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Извлекаем признаки для ИИ из свечей.
        """
        # ИСПРАВЛЕНО: убран префикс src., так как мы уже внутри папки src
        from technical_analysis import (
            calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
        )
        
        features = pd.DataFrame(index=df.index)
        
        features['RSI'] = calculate_rsi(df['Close'], period=14)
        features['MACD'], features['MACD_Signal'], features['MACD_Hist'] = calculate_macd(df['Close'])
        features['BB_Upper'], features['BB_Middle'], features['BB_Lower'], features['BB_Width'] = calculate_bollinger_bands(df['Close'])
        features['SMA_20'] = calculate_sma(df['Close'], 20)
        features['SMA_50'] = calculate_sma(df['Close'], 50)
        
        features['price_vs_SMA20'] = (df['Close'] - features['SMA_20']) / features['SMA_20']
        features['price_vs_SMA50'] = (df['Close'] - features['SMA_50']) / features['SMA_50']
        features['BB_position'] = (df['Close'] - features['BB_Lower']) / (features['BB_Upper'] - features['BB_Lower'])
        
        features['volatility_10d'] = df['Close'].rolling(10).std() / df['Close']
        features['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
        features['daily_return'] = df['Close'].pct_change()
        
        features['distance_to_20d_high'] = (df['Close'] - df['Close'].rolling(20).max()) / df['Close']
        features['distance_to_20d_low'] = (df['Close'] - df['Close'].rolling(20).min()) / df['Close']
        
        return features.dropna()