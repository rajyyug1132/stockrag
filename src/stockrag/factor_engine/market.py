from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

BENCHMARK_TICKER = "^GSPC"


@dataclass(frozen=True)
class MarketData:
    price: float | None
    market_cap: float | None
    beta: float | None
    momentum_12_1: float | None


def _beta(stock_weekly: pd.Series, bench_weekly: pd.Series) -> float | None:
    merged = pd.DataFrame({"stock": stock_weekly, "bench": bench_weekly}).dropna()
    returns = merged.pct_change().dropna()
    if len(returns) < 20:
        return None
    cov = np.cov(returns["stock"], returns["bench"])
    if cov[1, 1] == 0:
        return None
    return float(cov[0, 1] / cov[1, 1])


def _momentum_12_1(daily_close: pd.Series) -> float | None:
    if daily_close.empty:
        return None
    last_date = daily_close.index[-1]
    end_cutoff = last_date - pd.DateOffset(months=1)
    start_cutoff = last_date - pd.DateOffset(months=12)
    end_slice = daily_close[daily_close.index <= end_cutoff]
    start_slice = daily_close[daily_close.index <= start_cutoff]
    if end_slice.empty or start_slice.empty:
        return None
    p_end, p_start = float(end_slice.iloc[-1]), float(start_slice.iloc[-1])
    if p_start == 0:
        return None
    return p_end / p_start - 1


def get_market_data(ticker: str, shares_outstanding: float | None) -> MarketData:
    """Beta, 12-1 month momentum, latest price and derived market cap.

    yfinance is unofficial and occasionally flaky; any failure degrades to
    all-``None`` fields rather than raising, since these are supplementary
    to the XBRL-derived fundamentals.
    """
    try:
        stock_weekly = yf.Ticker(ticker).history(period="2y", interval="1wk", auto_adjust=True)["Close"]
        bench_weekly = yf.Ticker(BENCHMARK_TICKER).history(period="2y", interval="1wk", auto_adjust=True)["Close"]
        daily = yf.Ticker(ticker).history(period="14mo", interval="1d", auto_adjust=True)["Close"]
    except Exception:
        return MarketData(price=None, market_cap=None, beta=None, momentum_12_1=None)

    if stock_weekly.empty:
        return MarketData(price=None, market_cap=None, beta=None, momentum_12_1=None)

    price = float(stock_weekly.iloc[-1])
    market_cap = price * shares_outstanding if shares_outstanding else None

    return MarketData(
        price=price,
        market_cap=market_cap,
        beta=_beta(stock_weekly, bench_weekly),
        momentum_12_1=_momentum_12_1(daily),
    )
