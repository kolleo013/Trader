import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
# Never let tests initialize or change the repository database.
TEMP = tempfile.TemporaryDirectory()
os.environ['TRADER_DB_PATH'] = str(Path(TEMP.name) / 'test.db')
import app as web
from ml_model import TradingAI
from news_analyzer import analyze_sentiment_local, find_tickers_in_text
from signal_analyzer import SignalAnalyzer
from data_pipeline import DataPipeline
from pars import MOEXDataFetcher


def candles(n=140):
    rng = np.random.default_rng(2)
    close = 100 + np.cumsum(rng.normal(.03, .5, n))
    return pd.DataFrame({'Open': close - .1, 'High': close + .5, 'Low': close - .5, 'Close': close, 'Volume': rng.integers(1000, 5000, n)}, index=pd.date_range('2025-01-01', periods=n, freq='D'))


class CoreTests(unittest.TestCase):
    def test_missing_future_prices_are_not_negative_labels(self):
        df = candles()
        features = DataPipeline(None, None).get_features(df)
        model = TradingAI('SBER', 8)
        X, y = model.prepare_training_data(df, features)
        self.assertFalse(X.index.intersection(df.index[-8:]).size)
        expected = (df.Close.shift(-8) > df.Close * 1.005).loc[X.index].astype(int)
        pd.testing.assert_series_equal(y.astype(int), expected, check_names=False)

    def test_horizon_separates_model_files(self):
        self.assertNotEqual(TradingAI('SBER', 8, '1h').model_path, TradingAI('SBER', 8, '1d').model_path)
        self.assertFalse(TradingAI('SBER', 8, '1d').load())

    def test_model_probability_contract(self):
        model = TradingAI('SBER', 8)
        model.model = Mock()
        model.model.predict_proba.return_value = np.array([[.2, .8]])
        model.model.predict.return_value = np.array([1])
        model.feature_names = ['rsi']
        result = model.predict(pd.DataFrame({'rsi': [40]}))
        self.assertEqual(result['confidence'], 80)
        self.assertEqual(result['buy_probability'], 80)
        self.assertEqual(result['source'], 'model')
        self.assertTrue(model.should_trade(result))

    def test_news_financial_phrases_and_companies(self):
        self.assertLess(analyze_sentiment_local('Компания не выплатит дивиденды'), 0)
        self.assertGreater(analyze_sentiment_local('Снижение долга компании'), 0)
        self.assertLess(analyze_sentiment_local('Рост убытков компании'), 0)
        self.assertIn('SBER', find_tickers_in_text('Прибыль Сбербанка выросла'))
        self.assertIn('YDEX', find_tickers_in_text('Яндекс опубликовал отчет'))
        self.assertLessEqual(abs(analyze_sentiment_local('Рекордная прибыль')), 1)

    def test_flat_market_is_finite_and_volume_is_neutral(self):
        df = candles(); df.loc[:, ['Open', 'High', 'Low', 'Close']] = 100
        result = SignalAnalyzer(df).analyze_signals()
        self.assertTrue(np.isfinite(result['bullish_score']))
        self.assertEqual(result['details'][-1]['signal'], 'neutral')
        features = DataPipeline(None, None).get_features(df)
        self.assertFalse(np.isinf(features.to_numpy()).any())

    def test_routes_and_stale_data(self):
        df = candles()
        metadata = {'stale': True, 'source': 'archive', 'last_candle': str(df.index[-1])}
        with patch.object(web.store, 'get', return_value=(df, metadata)):
            client = web.app.test_client()
            result = client.get('/api/ticker/SBER').get_json()
            self.assertTrue(result['data_status']['stale'])
            self.assertEqual(result['ai_prediction']['source'], 'rules')
            self.assertIsNone(result['ai_prediction']['buy_probability'])
            self.assertEqual(len(result['price_history']), 120)
            self.assertNotIn('NaN', client.get('/api/ticker/SBER').text)
            self.assertEqual(client.get('/api/ticker/INVALID').status_code, 400)
            self.assertEqual(client.get('/api/ticker/SBER?tf=invalid').status_code, 400)
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(len(client.get('/api/screener').get_json()), 15)

    def test_news_market_and_sector_inclusion(self):
        items = [{'title': 'Общая новость', 'affects': ['ALL']}, {'title': 'Банки', 'affects': ['БАНКИ']}, {'title': 'Газ', 'affects': ['GAZP']}]
        with patch.object(web, 'news', return_value={'items': items, 'stale': False, 'updated': 'now'}):
            result = web.app.test_client().get('/api/ticker/SBER/news').get_json()
            self.assertEqual([i['relevance'] for i in result['items']], ['market', 'sector'])

    def test_moex_pagination_and_timeout(self):
        fetcher = MOEXDataFetcher()
        first, last = Mock(), Mock()
        first.json.return_value = {'candles': {'columns': ['begin','open','high','low','close','volume'], 'data': [['2025-01-01',1,2,1,2,10]]}}
        last.json.return_value = {'candles': {'data': []}}
        with patch.object(fetcher.session, 'get', side_effect=[first, last]) as get:
            df = fetcher.get_stock_data('SBER')
            self.assertEqual(len(df), 1)
            self.assertEqual(get.call_args.kwargs['params']['start'], 1)
            self.assertEqual(get.call_args.kwargs['timeout'], (3, 8))

    def test_backtest_costs_and_no_trades(self):
        from backtest import run
        df = candles(90)
        df.loc[:, ['Open', 'Close', 'High', 'Low']] = 100
        result = run(df)
        self.assertEqual(result['entries'], 0)
        self.assertEqual(result['net_return_pct'], 0)
        up = candles(90)
        for column in ('Open', 'Close', 'High', 'Low'):
            up[column] = np.arange(90) + 100.
        free, paid = run(up, 0), run(up, 50)
        self.assertGreater(free['entries'], 0)
        self.assertLess(paid['net_return_pct'], free['net_return_pct'])

    def test_model_training_purges_overlapping_labels(self):
        df = candles(220)
        features = DataPipeline(None, None).get_features(df)
        ai = TradingAI('SBER', 8)
        X, y = ai.prepare_training_data(df, features)
        fake = Mock()
        fake.predict.side_effect = lambda frame: np.zeros(len(frame), dtype=int)
        fake.predict_proba.side_effect = lambda frame: np.tile([.6, .4], (len(frame), 1))
        fake.feature_importances_ = np.ones(len(X.columns)) / len(X.columns)
        with patch('ml_model.ModelClass', return_value=fake), patch.object(ai, 'save'):
            ai.train(X, y)
        train_X = fake.fit.call_args.args[0]
        test_X = fake.predict.call_args.args[0]
        self.assertGreaterEqual(X.index.get_loc(test_X.index[0]) - X.index.get_loc(train_X.index[-1]), 9)


if __name__ == '__main__':
    unittest.main()
