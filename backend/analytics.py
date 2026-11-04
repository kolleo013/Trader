"""Shared, explainable signals. Scores are not calibrated probabilities."""
import numpy as np
from signal_analyzer import SignalAnalyzer
from data_pipeline import DataPipeline
from ml_model import TradingAI


def analyze(df):
    result = SignalAnalyzer(df).analyze_signals()
    if 'error' in result:
        raise ValueError(result['error'])
    return result


def prediction(df, ticker, timeframe, analysis):
    features = DataPipeline(None, None).get_features(df)
    ai = TradingAI(ticker, 8, timeframe=timeframe)
    if not features.empty and ai.load():
        try:
            return ai.predict(features)
        except (ValueError, TypeError, KeyError):
            pass
    score = analysis['bullish_score']
    return {
        'ticker': ticker, 'prediction': 'BUY' if score > 30 else 'SELL' if score < -30 else 'HOLD',
        'source': 'rules', 'confidence': None, 'buy_probability': None,
        'score': round(score, 1), 'forecast_bars': 8, 'timeframe': timeframe,
        'reason': 'Совместимая модель отсутствует. Оценка по техническим правилам, не вероятность.'
    }


def finite_json(value):
    """Flask otherwise emits non-standard NaN JSON for indicator warm-up rows."""
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value
