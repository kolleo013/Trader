import os
import requests
import urllib3
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from database import TradingDatabase
from pars import MOEXDataFetcher
from data_pipeline import DataPipeline
from ml_model import TradingAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# СПИСОК ТОП-15 АКЦИЙ ДЛЯ СКАНИРОВАНИЯ
TOP_TICKERS = [
    'SBER', 'GAZP', 'OZON', 'YNDX', 'TCSG', 
    'LKOH', 'NVTK', 'MGNT', 'FLOT', 'HYDR', 
    'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX'
]

class TradingBot:
    def __init__(self, forecast_hours: int = 8):
        load_dotenv()
        self.token = os.getenv('TINKOFF_TOKEN_SANDBOX')
        self.base_url = "https://invest-public-api.tinkoff.ru/rest"
        self.ACCOUNT_ID = "b37237e3-a44f-42bc-a6c0-10f83ecb8f13"
        
        self.db = TradingDatabase()
        self.fetcher = MOEXDataFetcher()
        self.pipeline = DataPipeline(self.db, self.fetcher)
        
        self.forecast_hours = forecast_hours
        self.min_confidence = 0.60  # Снизил до 60% для большей частоты сигналов
        self.position_size = 10
        self.max_open_trades = 5    # Увеличил лимит, так как акций больше

    def make_request(self, endpoint: str, payload: dict = {}) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
            return response.json() if response.status_code == 200 else None
        except Exception:
            return None

    def get_last_price(self, ticker: str) -> float:
        instruments = self.make_request("/tinkoff.public.invest.api.contract.v1.InstrumentsService/Shares")
        if not instruments: return 0.0
        share = next((i for i in instruments.get('instruments', []) if i['ticker'] == ticker), None)
        if not share: return 0.0
        
        data = self.make_request("/tinkoff.public.invest.api.contract.v1.MarketDataService/GetLastPrices", {"instrumentId": [share['figi']]})
        if data and 'lastPrices' in data:
            price = data['lastPrices'][0]['price']
            return float(price.get('units', 0)) + float(price.get('nano', 0)) / 1e9
        return 0.0

    def open_sandbox_position(self, ticker: str, figi: str, quantity: int, price: float):
        payload = {
            "accountId": self.ACCOUNT_ID, "figi": figi, "quantity": quantity,
            "price": {"currency": "rub", "units": int(price), "nano": int((price - int(price)) * 1e9)},
            "direction": "ORDER_DIRECTION_BUY", "orderType": "ORDER_TYPE_LIMIT"
        }
        result = self.make_request("/tinkoff.public.invest.api.contract.v1.SandboxService/PostSandboxOrder", payload)
        if result:
            print(f"   ✅ Позиция открыта: BUY {quantity} {ticker} @ {price:.2f}₽")
            return True
        return False

    def scan_market(self):
        """Сканирует весь рынок и находит лучший сигнал."""
        print(f"\n{'='*70}")
        print(f"🔍 СКАНИРОВАНИЕ РЫНКА ({len(TOP_TICKERS)} активов)")
        print(f"{'='*70}")
    
        best_signal = None
        
        for ticker in TOP_TICKERS:
            print(f"\n📈 Анализ {ticker}...")
            
            # 1. Данные
            df = self.pipeline.update_data(ticker, timeframe='1h', days=60) # 60 дней для скорости
            if df.empty:
                print(f"   ⚠️  Нет данных")
                continue
            
            # 2. Признаки
            features = self.pipeline.get_features(df)
            
            # 3. Модель
            ai = TradingAI(ticker, self.forecast_hours)
            if not ai.load():
                print(f"   🎓 Обучение новой модели для {ticker}...")
                X, y = ai.prepare_training_data(df, features)
                ai.train(X, y)
            
            # 4. Прогноз
            prediction = ai.predict(features)
            
            print(f"   Прогноз: {prediction['prediction']} | Покупка: {prediction['probability_buy']:.1f}% | Уверенность: {prediction['confidence']*100:.1f}%")
            
            # Сохраняем лучший сигнал
            if prediction['probability_buy'] > 50: # Рассматриваем только те, где вероятность покупки > 50%
                if best_signal is None or prediction['probability_buy'] > best_signal['probability_buy']:
                    best_signal = {
                        'ticker': ticker,
                        'prediction': prediction['prediction'],
                        'probability_buy': prediction['probability_buy'],
                        'confidence': prediction['confidence'],
                        'current_price': self.get_last_price(ticker)
                    }
        
        return best_signal

    def run_cycle(self):
        print(f"\n{'#'*70}")
        print(f"🤖 ЗАПУСК ТОРГОВОГО БОТА")
        print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*70}")
        
        # 1. Сканируем рынок
        best = self.scan_market()
        
        print(f"\n{'='*70}")
        print(f"🏆 ЛУЧШИЙ СИГНАЛ: {best['ticker'] if best else 'НЕ НАЙДЕН'}")
        print(f"{'='*70}")
        
        if best:
            print(f"   Вероятность покупки: {best['probability_buy']:.1f}%")
            print(f"   Уверенность: {best['confidence']*100:.1f}%")
            print(f"   Текущая цена: {best['current_price']:.2f}₽")
            
            # 2. Проверяем условия для сделки
            if best['prediction'] == 'BUY' and best['confidence'] >= self.min_confidence:
                open_trades = self.db.get_open_trades()
                if len(open_trades) < self.max_open_trades:
                    print(f"\n   ✅ СИГНАЛ НА ПОКУПКУ {best['ticker']}!")
                    
                    # Получаем FIGI для сделки
                    instruments = self.make_request("/tinkoff.public.invest.api.contract.v1.InstrumentsService/Shares")
                    share = next((i for i in instruments.get('instruments', []) if i['ticker'] == best['ticker']), None)
                    
                    if share:
                        success = self.open_sandbox_position(best['ticker'], share['figi'], self.position_size, best['current_price'])
                        if success:
                            self.db.save_trade(
                                ticker=best['ticker'], action='BUY', price=best['current_price'],
                                quantity=self.position_size, strategy='MarketScanner_XGB', confidence=best['confidence']
                            )
                else:
                    print(f"\n   ⚠️  Сигнал есть, но достигнут лимит открытых сделок ({self.max_open_trades})")
            else:
                print(f"\n   ⏸️  Сигнал: HOLD. Уверенность ({best['confidence']*100:.1f}%) ниже порога ({self.min_confidence*100:.0f}%)")
        else:
            print("\n   ⚠️  На рынке нет активов с вероятностью роста > 50%. Ждем.")

        # 3. Статистика
        print(f"\n{'='*70}")
        stats = self.db.get_trade_stats()
        print(f"📊 СТАТИСТИКА: Сделок: {stats['total_trades']} | Win Rate: {stats['win_rate']:.1f}% | Прибыль: {stats['total_profit'] or 0:.2f}₽")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    bot = TradingBot(forecast_hours=8)
    bot.run_cycle()