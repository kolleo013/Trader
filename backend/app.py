import os
import sys
import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv

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

db = TradingDatabase()
fetcher = MOEXDataFetcher()
pipeline = DataPipeline(db, fetcher)

ALL_TICKERS = [
    'SBER', 'GAZP', 'OZON', 'YNDX', 'TCSG', 
    'LKOH', 'NVTK', 'MGNT', 'FLOT', 'HYDR', 
    'SNGS', 'CHMF', 'MTSS', 'PLZL', 'MOEX'
]

TICKER_NAMES = {
    'SBER': 'Сбербанк', 'GAZP': 'Газпром', 'OZON': 'OZON Holdings',
    'YNDX': 'Яндекс', 'TCSG': 'Тинькофф', 'LKOH': 'Лукойл',
    'NVTK': 'Новатэк', 'MGNT': 'Магнит', 'FLOT': 'Совкомфлот',
    'HYDR': 'РусГидро', 'SNGS': 'Сургутнефтегаз', 'CHMF': 'Северсталь',
    'MTSS': 'МТС', 'PLZL': 'Полюс Золото', 'MOEX': 'Московская Биржа'
}

TICKER_COLORS = {
    'SBER': '#21a038', 'GAZP': '#0078be', 'OZON': '#005bff',
    'YNDX': '#fc3f1d', 'TCSG': '#ffdd2d', 'LKOH': '#e30611',
    'NVTK': '#0033a0', 'MGNT': '#e30613', 'FLOT': '#004b87',
    'HYDR': '#0033a0', 'SNGS': '#0078be', 'CHMF': '#0033a0',
    'MTSS': '#e30613', 'PLZL': '#c9a961', 'MOEX': '#0078be'
}

DEMO_NEWS = [
    {'title': 'Сбербанк увеличил чистую прибыль на 28% по итогам квартала',
     'description': 'Чистая прибыль Сбербанка выросла на 28% год к году, превысив ожидания аналитиков.',
     'sentiment': 'positive', 'source': 'Интерфакс', 'time_ago': '15 мин назад', 'affects': ['SBER']},
    {'title': 'ЦБ РФ сохранил ключевую ставку на уровне 21%',
     'description': 'Банк России принял решение сохранить ключевую ставку без изменений.',
     'sentiment': 'neutral', 'source': 'РБК', 'time_ago': '1 час назад', 'affects': ['SBER', 'MOEX']},
    {'title': 'Газпром снизил добычу газа на 12% из-за санкций',
     'description': 'Добыча газа Газпрома продолжает снижаться на фоне ограничений экспорта в Европу.',
     'sentiment': 'negative', 'source': 'Bloomberg', 'time_ago': '2 часа назад', 'affects': ['GAZP']},
    {'title': 'РусГидро объявило о снижении дивидендов',
     'description': 'Совет директоров рекомендовал снизить дивидендные выплаты на 30%.',
     'sentiment': 'negative', 'source': 'ТАСС', 'time_ago': '5 часов назад', 'affects': ['HYDR']},
    {'title': 'Золото обновило исторический максимум — $2,780/oz',
     'description': 'Цена золота продолжает рост на фоне геополитической неопределённости.',
     'sentiment': 'positive', 'source': 'Financial Times', 'time_ago': '6 часов назад', 'affects': ['PLZL']},
    {'title': 'Северсталь увеличила экспорт стали в Азию на 40%',
     'description': 'Компания успешно диверсифицировала рынки сбыта, нарастив поставки в Китай и Индию.',
     'sentiment': 'positive', 'source': 'Коммерсантъ', 'time_ago': '7 часов назад', 'affects': ['CHMF']}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tickers')
def get_tickers():
    return jsonify([
        {'ticker': t, 'name': TICKER_NAMES.get(t, t), 'color': TICKER_COLORS.get(t, '#848e9c')}
        for t in ALL_TICKERS
    ])

@app.route('/api/chart/<ticker>/<timeframe>')
def get_chart_data(ticker, timeframe):
    days = 365 if timeframe == '1d' else 30
    df = pipeline.update_data(ticker, timeframe, days)
    if df.empty:
        return jsonify({'error': 'Нет данных'}), 404
    
    from technical_analysis import (
        calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
    )
    df['SMA_20'] = calculate_sma(df['Close'], 20)
    df['SMA_50'] = calculate_sma(df['Close'], 50)
    df['RSI'] = calculate_rsi(df['Close'], 14)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
    
    data = []
    for date, row in df.iterrows():
        data.append({
            'date': date.strftime('%Y-%m-%d %H:%M'),
            'open': float(row['Open']), 'high': float(row['High']),
            'low': float(row['Low']), 'close': float(row['Close']),
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

@app.route('/api/signals/<ticker>')
def get_signals(ticker):
    try:
        df_1d = pipeline.update_data(ticker, '1d', 365)
        df_1h = pipeline.update_data(ticker, '1h', 30)
        if df_1d.empty or df_1h.empty:
            return jsonify({'error': 'Нет данных'}), 404
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
        features = pipeline.get_features(df_1h)
        ai = TradingAI(ticker, 8)
        ai_pred = None
        if ai.load() and not features.empty:
            ai_pred = ai.predict(features)
        return jsonify({'ticker': ticker, 'signals_1d': sig_1d, 'signals_1h': sig_1h, 'ai_prediction': ai_pred})
    except Exception as e:
        print(f"❌ Ошибка в get_signals: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticker/<ticker>')
def get_ticker(ticker):
    try:
        tf = request.args.get('tf', '1d')
        days = 365 if tf == '1d' else 30
        df = pipeline.update_data(ticker, tf, days)
        if df.empty:
            return jsonify({'error': 'Нет данных'}), 404
        
        from technical_analysis import (
            calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
        )
        df['SMA_20'] = calculate_sma(df['Close'], 20)
        df['SMA_50'] = calculate_sma(df['Close'], 50)
        df['RSI'] = calculate_rsi(df['Close'], 14)
        df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
        df['BB_Upper'], df['BB_Middle'], df['BB_Lower'], df['BB_Width'] = calculate_bollinger_bands(df['Close'])
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        price = float(last['Close'])
        prev_price = float(prev['Close'])
        change = price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price > 0 else 0
        
        recent = df.tail(60)
        price_history = []
        rsi_history = []
        macd_history = []
        
        for date, row in recent.iterrows():
            price_history.append({
                'date': date.strftime('%Y-%m-%d %H:%M'),
                'open': float(row['Open']), 'high': float(row['High']),
                'low': float(row['Low']), 'close': float(row['Close']),
                'volume': float(row['Volume']),
                'sma_20': float(row['SMA_20']) if not pd.isna(row.get('SMA_20')) else None
            })
            if not pd.isna(row.get('RSI')):
                rsi_history.append({'date': date.strftime('%m-%d'), 'value': float(row['RSI'])})
            if not pd.isna(row.get('MACD')):
                macd_history.append({
                    'date': date.strftime('%m-%d'),
                    'macd': float(row['MACD']),
                    'signal': float(row['MACD_Signal']) if not pd.isna(row.get('MACD_Signal')) else 0
                })
        
        sig = SignalAnalyzer(df).analyze_signals()
        positive = sig.get('positive', 0)
        negative = sig.get('negative', 0)
        neutral = sig.get('neutral', 0)
        total = positive + negative + neutral
        score = int((positive - negative) / total * 100) if total > 0 else 0
        
        features = pipeline.get_features(df)
        ai = TradingAI(ticker, 8)
        ai_pred = None
        if ai.load() and not features.empty:
            ai_pred = ai.predict(features)
        
        indicators_list = []
        if not pd.isna(last.get('SMA_20')):
            sma20 = float(last['SMA_20'])
            indicators_list.append({
                'indicator': 'Цена vs SMA 20',
                'signal': 'positive' if price > sma20 else 'negative',
                'value': 'Выше' if price > sma20 else 'Ниже',
                'description': 'Краткосрочный тренд ' + ('вверх' if price > sma20 else 'вниз')
            })
        if not pd.isna(last.get('RSI')):
            rsi_val = float(last['RSI'])
            if rsi_val > 70: sig_type, desc = 'negative', 'Перекупленность'
            elif rsi_val < 30: sig_type, desc = 'positive', 'Перепроданность'
            else: sig_type, desc = ('positive', 'Умеренно бычий') if rsi_val > 50 else ('positive', 'Умеренно медвежий')
            indicators_list.append({'indicator': 'RSI (14)', 'signal': sig_type, 'value': f'{rsi_val:.1f}', 'description': desc})
        if not pd.isna(last.get('MACD')) and not pd.isna(last.get('MACD_Signal')):
            macd, signal = float(last['MACD']), float(last['MACD_Signal'])
            indicators_list.append({
                'indicator': 'MACD', 'signal': 'positive' if macd > signal else 'negative',
                'value': 'Выше Signal' if macd > signal else 'Ниже Signal',
                'description': 'Бычий импульс' if macd > signal else 'Медвежий импульс'
            })
        if not pd.isna(last.get('BB_Upper')) and not pd.isna(last.get('BB_Lower')):
            bb_upper, bb_lower = float(last['BB_Upper']), float(last['BB_Lower'])
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_pos = (price - bb_lower) / bb_range * 100
                if bb_pos > 80: sig_t, desc = 'negative', 'У верхней границы'
                elif bb_pos < 20: sig_t, desc = 'positive', 'У нижней границы'
                else: sig_t, desc = 'neutral', 'В середине канала'
                indicators_list.append({'indicator': 'Bollinger Bands', 'signal': sig_t, 'value': f'{bb_pos:.0f}%', 'description': desc})
        volume = float(last['Volume'])
        avg_volume = df['Volume'].tail(20).mean()
        indicators_list.append({
            'indicator': 'Объём',
            'signal': 'positive' if volume > avg_volume * 1.5 else 'neutral',
            'value': f'{volume/1000000:.1f}M',
            'description': 'Высокая активность' if volume > avg_volume * 1.5 else 'Обычная активность'
        })
        if not pd.isna(last.get('SMA_20')) and not pd.isna(last.get('SMA_50')):
            sma20, sma50 = float(last['SMA_20']), float(last['SMA_50'])
            indicators_list.append({
                'indicator': 'Тренд', 'signal': 'positive' if sma20 > sma50 else 'negative',
                'value': '↑ Рост' if sma20 > sma50 else '↓ Падение',
                'description': 'Восходящий тренд' if sma20 > sma50 else 'Нисходящий тренд'
            })
        
        other_tf = '1h' if tf == '1d' else '1d'
        other_days = 30 if other_tf == '1h' else 365
        df_other = pipeline.update_data(ticker, other_tf, other_days)
        indicators_other = indicators_list
        if not df_other.empty:
            df_other['SMA_20'] = calculate_sma(df_other['Close'], 20)
            df_other['SMA_50'] = calculate_sma(df_other['Close'], 50)
            df_other['RSI'] = calculate_rsi(df_other['Close'], 14)
            df_other['MACD'], df_other['MACD_Signal'], df_other['MACD_Hist'] = calculate_macd(df_other['Close'])
            df_other['BB_Upper'], df_other['BB_Middle'], df_other['BB_Lower'], df_other['BB_Width'] = calculate_bollinger_bands(df_other['Close'])
            indicators_other = []
            last_o = df_other.iloc[-1]
            price_o = float(last_o['Close'])
            if not pd.isna(last_o.get('SMA_20')):
                sma20_o = float(last_o['SMA_20'])
                indicators_other.append({'indicator': 'Цена vs SMA 20', 'signal': 'positive' if price_o > sma20_o else 'negative', 'value': 'Выше' if price_o > sma20_o else 'Ниже', 'description': 'Краткосрочный тренд ' + ('вверх' if price_o > sma20_o else 'вниз')})
            if not pd.isna(last_o.get('RSI')):
                rsi_o = float(last_o['RSI'])
                indicators_other.append({'indicator': 'RSI (14)', 'signal': 'positive' if 30 < rsi_o < 70 else ('negative' if rsi_o > 70 else 'positive'), 'value': f'{rsi_o:.1f}', 'description': 'Умеренно бычий' if 50 < rsi_o < 70 else ('Перекупленность' if rsi_o > 70 else 'Перепроданность')})
            if not pd.isna(last_o.get('MACD')) and not pd.isna(last_o.get('MACD_Signal')):
                macd_o, signal_o = float(last_o['MACD']), float(last_o['MACD_Signal'])
                indicators_other.append({'indicator': 'MACD', 'signal': 'positive' if macd_o > signal_o else 'negative', 'value': 'Выше Signal' if macd_o > signal_o else 'Ниже Signal', 'description': 'Бычий импульс' if macd_o > signal_o else 'Медвежий импульс'})
            if not pd.isna(last_o.get('BB_Upper')) and not pd.isna(last_o.get('BB_Lower')):
                bb_u, bb_l = float(last_o['BB_Upper']), float(last_o['BB_Lower'])
                bb_r = bb_u - bb_l
                if bb_r > 0:
                    bb_p = (price_o - bb_l) / bb_r * 100
                    indicators_other.append({'indicator': 'Bollinger Bands', 'signal': 'neutral', 'value': f'{bb_p:.0f}%', 'description': 'В середине канала'})
            vol_o = float(last_o['Volume'])
            avg_vol_o = df_other['Volume'].tail(20).mean()
            indicators_other.append({'indicator': 'Объём', 'signal': 'positive' if vol_o > avg_vol_o * 1.5 else 'neutral', 'value': f'{vol_o/1000000:.1f}M', 'description': 'Высокая активность' if vol_o > avg_vol_o * 1.5 else 'Обычная активность'})
            if not pd.isna(last_o.get('SMA_20')) and not pd.isna(last_o.get('SMA_50')):
                indicators_other.append({'indicator': 'Тренд', 'signal': 'positive' if float(last_o['SMA_20']) > float(last_o['SMA_50']) else 'negative', 'value': '↑ Рост' if float(last_o['SMA_20']) > float(last_o['SMA_50']) else '↓ Падение', 'description': 'Восходящий тренд' if float(last_o['SMA_20']) > float(last_o['SMA_50']) else 'Нисходящий тренд'})
        
        return jsonify({
            'ticker': ticker, 'price': price, 'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': f'{volume/1000000:.1f}M', 'market_cap': '—',
            'rsi': float(last['RSI']) if not pd.isna(last.get('RSI')) else 50,
            'score': score, 'ai_prediction': ai_pred,
            'price_history': price_history, 'rsi_history': rsi_history, 'macd_history': macd_history,
            'signals_1d': indicators_list if tf == '1d' else indicators_other,
            'signals_1h': indicators_other if tf == '1d' else indicators_list
        })
    except Exception as e:
        print(f"❌ Ошибка в get_ticker: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
                ai_pred_str, ai_conf = 'HOLD', 0
                if ai.load() and not features.empty:
                    ai_pred = ai.predict(features)
                    ai_pred_str = ai_pred.get('prediction', 'HOLD')
                    ai_conf = ai_pred.get('confidence', 0)
                last_1h = df_1h.iloc[-1]
                prev_1h = df_1h.iloc[-2] if len(df_1h) > 1 else last_1h
                price = float(last_1h['Close'])
                prev_price = float(prev_1h['Close'])
                change = price - prev_price
                change_pct = (change / prev_price) * 100 if prev_price > 0 else 0
                macd_val = float(last_1h.get('MACD', 0)) if not pd.isna(last_1h.get('MACD')) else 0
                macd_sig = float(last_1h.get('MACD_Signal', 0)) if not pd.isna(last_1h.get('MACD_Signal')) else 0
                macd_signal = 'bullish' if macd_val > macd_sig else ('bearish' if macd_val < macd_sig else 'neutral')
                results.append({
                    'ticker': ticker, 'name': TICKER_NAMES.get(ticker, ticker),
                    'color': TICKER_COLORS.get(ticker, '#848e9c'),
                    'score': round(score, 1), 'positive': total_pos, 'negative': total_neg, 'neutral': total_neu,
                    'forecast_1d': sig_1d.get('forecast_ru', '—'), 'forecast_1h': sig_1h.get('forecast_ru', '—'),
                    'price': price, 'change': round(change, 2), 'change_percent': round(change_pct, 2),
                    'rsi': round(float(last_1h.get('RSI', 50)), 1) if not pd.isna(last_1h.get('RSI')) else 50,
                    'macd_signal': macd_signal, 'ai_prediction': ai_pred_str, 'ai_confidence': ai_conf,
                    'volume': float(last_1h.get('Volume', 0))
                })
            except Exception as e:
                print(f"⚠️  Ошибка для {ticker}: {e}")
                continue
        results.sort(key=lambda x: x['score'], reverse=True)
        return jsonify(results)
    except Exception as e:
        print(f"❌ Ошибка в screener: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/news')
def get_news():
    return jsonify(DEMO_NEWS)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)