"""Historical rules baseline, long/cash, next-bar execution, no parameter search.

Usage: python backend/backtest.py --csv data/SBER.csv --cost-bps 10
This is a research check on the supplied history, not an out-of-sample ML test.
"""
import argparse
import json
import numpy as np
import pandas as pd
from signal_analyzer import SignalAnalyzer


def run(df, cost_bps=10):
    if len(df) < 60 or not 0 <= cost_bps < 1000:
        raise ValueError('Нужно минимум 60 свечей и допустимые издержки 0–999 bps')
    df = df.sort_index().copy()
    if df.index.has_duplicates or (df[['Open', 'Close']] <= 0).any().any() or df[['Open', 'Close']].isna().any().any():
        raise ValueError('Некорректные цены или повторяющиеся даты')
    # At each close, generate a decision using only history available then.
    cost = cost_bps / 10000
    cash, shares, trades = 1.0, 0.0, 0
    equity = [1.0]
    entry = None
    profits = []
    for i in range(50, len(df)):
        score = SignalAnalyzer(df.iloc[:i]).analyze_signals()['bullish_score']
        opening, closing = float(df.Open.iloc[i]), float(df.Close.iloc[i])
        if shares == 0 and score > 30:
            entry = cash
            shares, cash = cash / (opening * (1 + cost)), 0.0
            trades += 1
        elif shares and score < -30:
            cash, shares = shares * opening * (1 - cost), 0.0
            profits.append(cash / entry - 1)
        equity.append(cash + shares * closing)
    if shares:
        cash = shares * float(df.Close.iloc[-1]) * (1 - cost)
        profits.append(cash / entry - 1)
        equity[-1] = cash
    curve = np.asarray(equity)
    baseline = float(df.Close.iloc[-1]) / float(df.Open.iloc[50]) * (1 - cost) / (1 + cost) - 1
    return {'strategy': 'grouped technical rules, long/cash', 'bars': len(df) - 50,
            'round_trip_cost_bps': 2 * cost_bps, 'entries': trades,
            'net_return_pct': float((curve[-1] - 1) * 100),
            'buy_hold_return_pct': float(baseline * 100),
            'max_drawdown_pct': float((curve / np.maximum.accumulate(curve) - 1).min() * 100),
            'win_rate_pct': float(np.mean(np.asarray(profits) > 0) * 100) if profits else None,
            'limitations': 'Historical rules check only; no dividends, taxes, fills, corporate-action adjustment or out-of-sample validation. Cost is charged per side.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--cost-bps', type=float, default=10)
    args = parser.parse_args()
    print(json.dumps(run(pd.read_csv(args.csv, index_col=0, parse_dates=True), args.cost_bps), ensure_ascii=False, indent=2))
