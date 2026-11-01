import os
import sys
import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

# Добавляем backend в path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import TradingDatabase
from pars import MOEXDataFetcher
from data_pipeline import DataPipeline
from ml_model import TradingAI
from signal_analyzer import SignalAnalyzer

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = Flask(__name__, 
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Инициализация
db = TradingDatabase()
fetcher = MOEXDataFetcher()
pipeline = DataPipeline(db, fetcher)

ALL_TICKERS = [
    'SBER', 'GAZP', 'OZON', 'YNDX', 'TCSG', 
    'LKOH', 'NVTK', 'MGNT', 'FLOT', 'HYDR', 
    'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX'
]

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# API: список акций
@app.route('/api/tickers')
def get_tickers():
    return jsonify(ALL_TICKERS)

# API: данные для графика
@app.route('/api/chart/<ticker>/<timeframe>')
def get_chart_data(ticker, timeframe):
    days = 365 if timeframe == '1d' else 30
    df = pipeline.update_data(ticker, timeframe, days)
    
    if df.empty:
        return jsonify({'error': 'Нет данных'}), 404
    
    # Добавляем индикаторы
    from technical_analysis import (
        calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
    )
    
    df['SMA_20'] = calculate_sma(df['Close'], 20)
    df['SMA_50'] = calculate_sma(df['Close'], 50)
    df['RSI'] = calculate_rsi(df['Close'], 14)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
    
    # Преобразуем в JSON-friendly формат
    data = []
    for date, row in df.iterrows():
        data.append({
            'date': date.strftime('%Y-%m-%d %H:%M'),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume']),
            'sma_20': float(row.get('SMA_20', 0)) if not pd.isna(row.get('SMA_20')) else None,
            'sma_50': float(row.get('SMA_50', 0)) if not pd.isna(row.get('SMA_50')) else None,
            'rsi': float(row.get('RSI', 0)) if not pd.isna(row.get('RSI')) else None,
            'macd': float(row.get('MACD', 0)) if not pd.isna(row.get('MACD')) else None,
            'macd_signal': float(row.get('MACD_Signal', 0)) if not pd.isna(row.get('MACD_Signal')) else None,
            'macd_hist': float(row.get('MACD_Hist', 0)) if not pd.isna(row.get('MACD_Hist')) else None,
            'bb_upper': float(row.get('BB_Upper', 0)) if not pd.isna(row.get('BB_Upper')) else None,
            'bb_lower': float(row.get('BB_Lower', 0)) if not pd.isna(row.get('BB_Lower')) else None,
        })
    
    return jsonify(data)

# API: сигналы для тикера
@app.route('/api/signals/<ticker>')
def get_signals(ticker):
    try:
        print(f"\n🔍 Запрос сигналов для {ticker}...")
        
        df_1d = pipeline.update_data(ticker, '1d', 365)
        df_1h = pipeline.update_data(ticker, '1h', 30)
        
        print(f"   1D данных: {len(df_1d)} строк")
        print(f"   1H данных: {len(df_1h)} строк")
        
        if df_1d.empty or df_1h.empty:
            return jsonify({'error': 'Нет данных'}), 404
        
        # Добавляем индикаторы
        from technical_analysis import (
            calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
        )
        
        for df_name, df in [('1D', df_1d), ('1H', df_1h)]:
            print(f"   Добавляем индикаторы для {df_name}...")
            df['SMA_20'] = calculate_sma(df['Close'], 20)
            df['SMA_50'] = calculate_sma(df['Close'], 50)
            df['RSI'] = calculate_rsi(df['Close'], 14)
            df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
            df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
            print(f"   ✅ Индикаторы для {df_name} добавлены")
        
        print("   Анализируем сигналы 1D...")
        sig_1d = SignalAnalyzer(df_1d).analyze_signals()
        print(f"   ✅ Сигналы 1D: {sig_1d.get('forecast_ru', 'error')}")
        
        print("   Анализируем сигналы 1H...")
        sig_1h = SignalAnalyzer(df_1h).analyze_signals()
        print(f"   ✅ Сигналы 1H: {sig_1h.get('forecast_ru', 'error')}")
        
        # Прогноз ИИ
        print("   Получаем прогноз ИИ...")
        features = pipeline.get_features(df_1h)
        ai = TradingAI(ticker, 8)
        ai_pred = None
        if ai.load() and not features.empty:
            ai_pred = ai.predict(features)
            print(f"   ✅ Прогноз ИИ: {ai_pred.get('prediction', 'N/A')}")
        else:
            print("   ️  Модель не загружена или нет признаков")
        
        result = {
            'ticker': ticker,
            'signals_1d': sig_1d,
            'signals_1h': sig_1h,
            'ai_prediction': ai_pred
        }
        
        print(f"   ✅ Отправляем результат")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Ошибка в get_signals: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# API: скринер рынка
@app.route('/api/screener')
def get_screener():
    try:
        results = []
        for ticker in ALL_TICKERS:
            try:
                df_1d = pipeline.update_data(ticker, '1d', 365)
                df_1h = pipeline.update_data(ticker, '1h', 30)
                
                if df_1d.empty or df_1h.empty:
                    continue
                
                from technical_analysis import (
                    calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
                )
                for df in [df_1d, df_1h]:
                    df['SMA_20'] = calculate_sma(df['Close'], 20)
                    df['SMA_50'] = calculate_sma(df['Close'], 50)
                    df['RSI'] = calculate_rsi(df['Close'], 14)
                    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
                    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
                
                sig_1d = SignalAnalyzer(df_1d).analyze_signals()
                sig_1h = SignalAnalyzer(df_1h).analyze_signals()
                
                if 'error' in sig_1d or 'error' in sig_1h:
                    continue
                
                total_pos = sig_1d['positive'] + sig_1h['positive']
                total_neg = sig_1d['negative'] + sig_1h['negative']
                total_neu = sig_1d['neutral'] + sig_1h['neutral']
                total = total_pos + total_neg + total_neu
                score = (total_pos - total_neg) / total * 100 if total > 0 else 0
                
                features = pipeline.get_features(df_1h)
                ai = TradingAI(ticker, 8)
                ai_pred = None
                if ai.load() and not features.empty:
                    ai_pred = ai.predict(features)
                
                results.append({
                    'ticker': ticker,
                    'score': round(score, 1),
                    'positive': total_pos,
                    'negative': total_neg,
                    'neutral': total_neu,
                    'forecast_1d': sig_1d['forecast_ru'],
                    'forecast_1h': sig_1h['forecast_ru'],
                    'price': float(sig_1h['indicators']['Close']),
                    'rsi': round(float(sig_1h['indicators']['RSI']), 1),
                    'ai_prediction': ai_pred
                })
            except Exception as e:
                print(f"⚠️  Ошибка для {ticker}: {e}")
                continue
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return jsonify(results)
    except Exception as e:
        print(f"❌ Ошибка в screener: {e}")
        return jsonify({'error': str(e)}), 500

# API: статистика бота
@app.route('/api/stats')
def get_stats():
    stats = db.get_trade_stats()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)