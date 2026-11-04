"""MOEX research dashboard. Run: python backend/app.py."""
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from database import TradingDatabase
from pars import MOEXDataFetcher
from market import MarketStore, TICKERS
from analytics import analyze, prediction, finite_json
from technical_analysis import calculate_sma, calculate_rsi, calculate_macd
from news_analyzer import fetch_all_news, TICKER_TO_SECTOR

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')
db = TradingDatabase()
store = MarketStore(db, MOEXDataFetcher())
news_lock = threading.Lock()
news_cache = {'items': [], 'checked': 0, 'updated': None, 'stale': True}


def response(data, status=200):
    return jsonify(finite_json(data)), status


def validate(ticker, tf):
    if ticker not in TICKERS or tf not in ('1d', '1h'):
        raise ValueError('Неизвестная акция или таймфрейм')


@app.errorhandler(ValueError)
def invalid(error):
    return response({'error': str(error)}, 400)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return response({'status': 'ok', 'tickers': len(TICKERS)})


@app.route('/api/tickers')
def tickers():
    return response([{'ticker': t, 'name': n} for t, n in TICKERS.items()])


def details(ticker, tf):
    validate(ticker, tf)
    df, metadata = store.get(ticker, tf)
    if len(df) < 50:
        return {'ticker': ticker, 'name': TICKERS[ticker], 'error': 'Недостаточно данных: нужно минимум 50 завершённых свечей', 'data_status': metadata}
    analysis = analyze(df)
    recent = df.tail(120).copy()
    recent['sma_20'] = calculate_sma(df.Close, 20)
    recent['rsi'] = calculate_rsi(df.Close)
    recent['macd'], recent['macd_signal'], _ = calculate_macd(df.Close)
    history = [{'date': str(date), **{k.lower(): float(row[k]) for k in ('Open', 'High', 'Low', 'Close', 'Volume')},
                'sma_20': row.sma_20, 'rsi': row.rsi, 'macd': row.macd, 'signal': row.macd_signal} for date, row in recent.iterrows()]
    last, prev = df.iloc[-1], df.iloc[-2]
    change = float(last.Close - prev.Close)
    returns = df.Close.pct_change().dropna()
    return {'ticker': ticker, 'name': TICKERS[ticker], 'timeframe': tf,
            'price': float(last.Close), 'change': change, 'change_percent': change / prev.Close * 100 if prev.Close else None,
            'volume': float(last.Volume), 'score': round(analysis['bullish_score'], 1),
            'analysis': analysis, 'ai_prediction': prediction(df, ticker, tf, analysis),
            'price_history': history, 'data_status': metadata,
            'risk': {'bar_volatility_pct': float(returns.tail(20).std() * 100),
                     'drawdown_pct': float((df.Close / df.Close.cummax() - 1).min() * 100)}}


@app.route('/api/ticker/<ticker>')
def ticker_details(ticker):
    result = details(ticker, request.args.get('tf', '1d'))
    return response(result, 503 if 'error' in result else 200)


@app.route('/api/chart/<ticker>/<tf>')
def chart(ticker, tf):
    result = details(ticker, tf)
    return response(result if 'error' in result else result['price_history'], 503 if 'error' in result else 200)


@app.route('/api/signals/<ticker>')
def signals(ticker):
    validate(ticker, '1d')
    return response({tf: details(ticker, tf) for tf in ('1d', '1h')})


@app.route('/api/screener')
def screener():
    tf = request.args.get('tf', '1d')
    validate('SBER', tf)
    def row(ticker):
        try:
            item = details(ticker, tf)
            item.pop('price_history', None)
            return item
        except Exception:
            app.logger.exception('Screener failed for %s', ticker)
            return {'ticker': ticker, 'name': TICKERS[ticker], 'error': 'Источник данных временно недоступен'}
    # Bounded parallelism: a slow symbol does not serialize every other request.
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(row, TICKERS))
    return response(sorted(rows, key=lambda item: item.get('score', -101), reverse=True))


def news():
    with news_lock:
        if not news_cache['checked'] or time.monotonic() - news_cache['checked'] > 900:
            try:
                items = fetch_all_news(limit=150)
                if items:
                    news_cache.update(items=items, updated=pd.Timestamp.now(tz='UTC').isoformat(), stale=False)
                else:
                    news_cache['stale'] = True
            except Exception:
                app.logger.exception('News refresh failed')
                news_cache['stale'] = True
            news_cache['checked'] = time.monotonic()
        return dict(news_cache)


@app.route('/api/news')
def all_news():
    result = news()
    return response({'items': result['items'], 'updated_at': result['updated'], 'stale': result['stale'], 'method': 'rules'})


@app.route('/api/ticker/<ticker>/news')
def ticker_news(ticker):
    validate(ticker, '1d')
    result = news()
    sector = TICKER_TO_SECTOR.get(ticker)
    items = []
    for item in result['items']:
        affects = item.get('affects', [])
        relevance = 'company' if ticker in affects else 'sector' if sector in affects else 'market' if 'ALL' in affects else None
        if relevance:
            items.append({**item, 'relevance': relevance})
    return response({'items': items[:10], 'stale': result['stale'], 'updated_at': result['updated'], 'method': 'rules'})


if __name__ == '__main__':
    app.run(host=os.getenv('TRADER_HOST', '127.0.0.1'), port=int(os.getenv('TRADER_PORT', '5001')), debug=False)
