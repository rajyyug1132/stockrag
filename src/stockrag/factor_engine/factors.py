from dataclasses import dataclass

from stockrag.factor_engine.fundamentals import FiscalYearFundamentals
from stockrag.factor_engine.market import MarketData
from stockrag.factor_engine.ratios import safe_div


@dataclass(frozen=True)
class FactorCharacteristics:
    """Firm characteristics used by Fama-French/Carhart-style factor
    models (size, value, profitability, momentum). This is the firm's
    exposure profile, not a regression against realized factor returns.
    """

    gross_profitability: float | None
    size: float | None
    book_to_market: float | None
    momentum_12_1: float | None


def compute_factor_characteristics(
    fy: FiscalYearFundamentals, market: MarketData
) -> FactorCharacteristics:
    return FactorCharacteristics(
        gross_profitability=safe_div(fy.gross_profit, fy.total_assets),
        size=market.market_cap,
        book_to_market=safe_div(fy.stockholders_equity, market.market_cap),
        momentum_12_1=market.momentum_12_1,
    )
