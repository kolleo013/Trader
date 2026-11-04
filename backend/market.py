"""Bounded, per-symbol refresh cache; keeps stale data usable and labelled."""
import threading
import time
from pathlib import Path
import pandas as pd

TICKERS = {
    'SBER': 'Сбербанк', 'GAZP': 'Газпром', 'OZON': 'Ozon', 'YDEX': 'Яндекс',
    'T': 'Т-Технологии', 'LKOH': 'Лукойл', 'NVTK': 'Новатэк', 'MGNT': 'Магнит',
    'FLOT': 'Совкомфлот', 'HYDR': 'РусГидро', 'SNGS': 'Сургутнефтегаз',
    'CHMF': 'Северсталь', 'MTSS': 'МТС', 'PLZL': 'Полюс', 'MOEX': 'Московская биржа'
}

class MarketStore:
    def __init__(self, db, fetcher, ttl=300):
        self.db, self.fetcher, self.ttl = db, fetcher, ttl
        self.cache = {}
        self.locks = {(t, tf): threading.Lock() for t in TICKERS for tf in ('1d', '1h')}

    def get(self, ticker, timeframe):
        key = (ticker, timeframe)
        with self.locks[key]:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < self.ttl:
                return cached[1].copy(), dict(cached[2])
            days = 730 if timeframe == '1d' else 90
            history = self.db.load_candles(ticker, timeframe, days)
            fresh = self.fetcher.get_stock_data(ticker, days=days, interval=24 if timeframe == '1d' else 60)
            source = 'moex' if not fresh.empty else 'cache'
            if not fresh.empty:
                self.db.save_candles(ticker, timeframe, fresh)
                history = pd.concat([history, fresh])
            if history.empty:
                path = Path(__file__).resolve().parents[1] / 'data' / f"{ticker}{'_1h' if timeframe == '1h' else ''}.csv"
                if path.exists():
                    history = pd.read_csv(path, index_col=0, parse_dates=True)
                    source = 'archive'
            if not history.empty:
                history = history[~history.index.duplicated(keep='last')].sort_index()
                # Exclude the current candle; do not mistake an incomplete bar for a close.
                now = pd.Timestamp.now(tz='Europe/Moscow').tz_localize(None)
                cutoff = now.normalize() if timeframe == '1d' else now.floor('h')
                history = history[history.index < cutoff]
            last = history.index[-1] if not history.empty else None
            age = (pd.Timestamp.now(tz='Europe/Moscow').tz_localize(None) - last).total_seconds() if last is not None else None
            stale = source != 'moex' or age is None or age > (4 * 86400 if timeframe == '1d' else 4 * 3600)
            metadata = {'source': source, 'stale': stale, 'last_candle': str(last) if last is not None else None,
                        'timezone': 'Europe/Moscow', 'updated_at': pd.Timestamp.now(tz='UTC').isoformat(),
                        'warning': 'Свежие котировки недоступны или последняя свеча устарела' if stale else None}
            self.cache[key] = (time.monotonic(), history.copy(), metadata)
            return history, metadata
