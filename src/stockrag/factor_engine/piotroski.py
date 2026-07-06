from dataclasses import dataclass

from stockrag.factor_engine.fundamentals import FiscalYearFundamentals
from stockrag.factor_engine.ratios import safe_div

# Piotroski (2000) allows a small tolerance for share issuance tied to
# compensation plans rather than treating any increase as dilution.
DILUTION_TOLERANCE = 1.02


@dataclass(frozen=True)
class PiotroskiResult:
    score: int | None
    signals: dict[str, bool | None]


def _roa(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.net_income, fy.total_assets)


def _leverage(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.long_term_debt, fy.total_assets)


def _current_ratio(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.current_assets, fy.current_liabilities)


def _gross_margin(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.gross_profit, fy.revenue)


def _asset_turnover(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.revenue, fy.total_assets)


def compute_piotroski(current: FiscalYearFundamentals, prior: FiscalYearFundamentals) -> PiotroskiResult:
    """The 9 binary Piotroski F-Score signals. Any signal whose inputs are
    missing is ``None`` (not counted for or against the score).
    """
    signals: dict[str, bool | None] = {}

    roa_cur, roa_prior = _roa(current), _roa(prior)
    signals["positive_roa"] = None if roa_cur is None else roa_cur > 0
    signals["positive_cfo"] = (
        None if current.operating_cash_flow is None else current.operating_cash_flow > 0
    )
    signals["roa_improving"] = None if roa_cur is None or roa_prior is None else roa_cur > roa_prior
    signals["cfo_exceeds_net_income"] = (
        None
        if current.operating_cash_flow is None or current.net_income is None
        else current.operating_cash_flow > current.net_income
    )

    lev_cur, lev_prior = _leverage(current), _leverage(prior)
    signals["leverage_decreasing"] = None if lev_cur is None or lev_prior is None else lev_cur < lev_prior

    cr_cur, cr_prior = _current_ratio(current), _current_ratio(prior)
    signals["current_ratio_improving"] = (
        None if cr_cur is None or cr_prior is None else cr_cur > cr_prior
    )

    signals["no_dilution"] = (
        None
        if current.shares_outstanding is None or prior.shares_outstanding is None
        else current.shares_outstanding <= prior.shares_outstanding * DILUTION_TOLERANCE
    )

    gm_cur, gm_prior = _gross_margin(current), _gross_margin(prior)
    signals["gross_margin_improving"] = None if gm_cur is None or gm_prior is None else gm_cur > gm_prior

    at_cur, at_prior = _asset_turnover(current), _asset_turnover(prior)
    signals["asset_turnover_improving"] = (
        None if at_cur is None or at_prior is None else at_cur > at_prior
    )

    known = [v for v in signals.values() if v is not None]
    score = sum(1 for v in known if v) if known else None
    return PiotroskiResult(score=score, signals=signals)
