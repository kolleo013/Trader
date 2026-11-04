"""Train a versioned local model with a purged chronological holdout."""
import argparse
import json
import pandas as pd
from data_pipeline import DataPipeline
from ml_model import TradingAI
from market import TICKERS

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticker', required=True, choices=TICKERS)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--timeframe', required=True, choices=['1h', '1d'])
    parser.add_argument('--horizon', type=int, default=8)
    args = parser.parse_args()
    df = pd.read_csv(args.csv, index_col=0, parse_dates=True).sort_index()
    if df.index.has_duplicates:
        raise ValueError('Повторяющиеся даты в истории')
    features = DataPipeline(None, None).get_features(df)
    ai = TradingAI(args.ticker, args.horizon, args.timeframe)
    X, y = ai.prepare_training_data(df, features)
    ai.train(X, y)
    print(json.dumps(ai.validation, indent=2, ensure_ascii=False))
    print('Holdout classification only. No trading performance or calibration guarantee.')
