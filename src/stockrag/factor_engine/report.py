from pydantic import BaseModel

from stockrag.edgar.client import EdgarClient
from stockrag.edgar.companyfacts import get_annual_fundamentals
from stockrag.edgar.tickers import cik_for_ticker
from stockrag.factor_engine.factors import FactorCharacteristics, compute_factor_characteristics
from stockrag.factor_engine.fundamentals import FiscalYearFundamentals
from stockrag.factor_engine.market import MarketData, get_market_data
from stockrag.factor_engine.piotroski import PiotroskiResult, compute_piotroski
from stockrag.factor_engine.ratios import (
    eps,
    free_cash_flow,
    net_margin,
    p_fcf_ratio,
    pe_ratio,
    revenue_growth,
    roe,
)

# Thresholds from Brian Feroldi's "How to Research a Company" flowchart.
ROE_THRESHOLD = 0.15
NET_MARGIN_THRESHOLD = 0.10
F_SCORE_STRONG_THRESHOLD = 7


class FactorReport(BaseModel):
    ticker: str
    cik: int
    fiscal_year_end: str | None = None

    price: float | None = None
    market_cap: float | None = None
    beta: float | None = None

    revenue: float | None = None
    revenue_growth: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    eps: float | None = None
    pe_ratio: float | None = None
    free_cash_flow: float | None = None
    p_fcf_ratio: float | None = None

    piotroski_score: int | None = None
    piotroski_signals: dict[str, bool | None] = {}

    gross_profitability: float | None = None
    book_to_market: float | None = None
    momentum_12_1: float | None = None

    checks: dict[str, bool | None] = {}
    missing: list[str] = []


def _empty_report(ticker: str, cik: int, missing: list[str]) -> FactorReport:
    return FactorReport(ticker=ticker.upper(), cik=cik, missing=missing)


def build_factor_report(ticker: str) -> FactorReport:
    with EdgarClient() as client:
        cik = cik_for_ticker(ticker, client=client)
        years: list[FiscalYearFundamentals] = get_annual_fundamentals(cik, client)

    if not years:
        return _empty_report(ticker, cik, missing=["fundamentals"])

    current = years[-1]
    prior = years[-2] if len(years) >= 2 else None

    missing: list[str] = []
    if prior is None:
        missing.append("insufficient_fiscal_years")

    market: MarketData = get_market_data(ticker, shares_outstanding=current.shares_outstanding)

    rev_growth = revenue_growth(current, prior) if prior else None
    net_margin_value = net_margin(current)
    roe_value = roe(current)
    eps_value = eps(current)
    fcf = free_cash_flow(current)
    pe = pe_ratio(market.price, eps_value)
    pfcf = p_fcf_ratio(market.market_cap, fcf)

    piotroski: PiotroskiResult = (
        compute_piotroski(current, prior) if prior else PiotroskiResult(score=None, signals={})
    )
    factor_chars: FactorCharacteristics = compute_factor_characteristics(current, market)

    for name, value in (
        ("revenue", current.revenue),
        ("net_margin", net_margin_value),
        ("roe", roe_value),
        ("price", market.price),
        ("market_cap", market.market_cap),
        ("beta", market.beta),
        ("piotroski_score", piotroski.score),
    ):
        if value is None:
            missing.append(name)

    checks = {
        "roe_gt_15pct": None if roe_value is None else roe_value > ROE_THRESHOLD,
        "net_margin_gt_10pct": None if net_margin_value is None else net_margin_value > NET_MARGIN_THRESHOLD,
        "f_score_ge_7": None if piotroski.score is None else piotroski.score >= F_SCORE_STRONG_THRESHOLD,
    }

    return FactorReport(
        ticker=ticker.upper(),
        cik=cik,
        fiscal_year_end=current.fiscal_year_end,
        price=market.price,
        market_cap=market.market_cap,
        beta=market.beta,
        revenue=current.revenue,
        revenue_growth=rev_growth,
        net_margin=net_margin_value,
        roe=roe_value,
        eps=eps_value,
        pe_ratio=pe,
        free_cash_flow=fcf,
        p_fcf_ratio=pfcf,
        piotroski_score=piotroski.score,
        piotroski_signals=piotroski.signals,
        gross_profitability=factor_chars.gross_profitability,
        book_to_market=factor_chars.book_to_market,
        momentum_12_1=factor_chars.momentum_12_1,
        checks=checks,
        missing=missing,
    )
