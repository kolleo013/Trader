"""
Скрипт для загрузки данных по всем 15 акциям (1D и 1H)
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from pars import MOEXDataFetcher

# Топ-15 акций РФ
TOP_TICKERS = [
    'SBER', 'GAZP', 'OZON', 'YNDX', 'TCSG', 
    'LKOH', 'NVTK', 'MGNT', 'FLOT', 'HYDR', 
    'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX'
]

def main():
    fetcher = MOEXDataFetcher()
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    print("=" * 70)
    print(" ЗАГРУЗКА ДАННЫХ ПО ВСЕМ 15 АКЦИЯМ")
    print("=" * 70)
    
    # 1D данные (365 дней)
    print("\n📅 ЗАГРУЗКА ДНЕВНЫХ СВЕЧЕЙ (1D)...")
    for ticker in TOP_TICKERS:
        print(f"\n📈 {ticker} (1D)...")
        df = fetcher.get_stock_data(ticker, days=365, interval=24)
        if not df.empty:
            df.to_csv(os.path.join(data_dir, f"{ticker}.csv"), index=True)
            print(f"   ✅ {len(df)} записей")
        else:
            print(f"   ❌ Нет данных")
    
    # 1H данные (30 дней)
    print("\n⏰ ЗАГРУЗКА ЧАСОВЫХ СВЕЧЕЙ (1H)...")
    for ticker in TOP_TICKERS:
        print(f"\n⏰ {ticker} (1H)...")
        df = fetcher.get_stock_data(ticker, days=30, interval=60)
        if not df.empty:
            df.to_csv(os.path.join(data_dir, f"{ticker}_1h.csv"), index=True)
            print(f"   ✅ {len(df)} записей")
        else:
            print(f"   ❌ Нет данных")
    
    print("\n" + "=" * 70)
    print("🎉 ВСЕ ДАННЫЕ ЗАГРУЖЕНЫ!")
    print("=" * 70)

if __name__ == "__main__":
    main()