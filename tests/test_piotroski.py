from stockrag.factor_engine.fundamentals import FiscalYearFundamentals
from stockrag.factor_engine.piotroski import compute_piotroski


def _fy(**overrides: float | None) -> FiscalYearFundamentals:
    base = dict(
        fiscal_year_end="2023-12-31",
        revenue=1000.0,
        cost_of_revenue=450.0,
        gross_profit=550.0,
        net_income=100.0,
        operating_cash_flow=130.0,
        capex=50.0,
        total_assets=1100.0,
        current_assets=500.0,
        total_liabilities=600.0,
        current_liabilities=220.0,
        long_term_debt=250.0,
        stockholders_equity=500.0,
        shares_outstanding=100.0,
    )
    base.update(overrides)
    return FiscalYearFundamentals(**base)


def test_all_nine_signals_pass() -> None:
    prior = _fy(
        fiscal_year_end="2022-12-31",
        revenue=900.0,
        cost_of_revenue=450.0,
        gross_profit=450.0,
        net_income=80.0,
        operating_cash_flow=100.0,
        total_assets=1000.0,
        current_assets=400.0,
        current_liabilities=200.0,
        long_term_debt=300.0,
        shares_outstanding=100.0,
    )
    current = _fy()  # improves on every dimension, no dilution

    result = compute_piotroski(current, prior)

    assert result.score == 9
    assert all(result.signals.values())


def test_deteriorating_year_scores_low() -> None:
    prior = _fy(
        fiscal_year_end="2022-12-31",
        revenue=1000.0,
        cost_of_revenue=400.0,
        gross_profit=600.0,
        net_income=150.0,
        operating_cash_flow=180.0,
        total_assets=900.0,
        current_assets=450.0,
        current_liabilities=180.0,
        long_term_debt=150.0,
        shares_outstanding=90.0,
    )
    # current: negative ROA, negative CFO, more leverage, worse current ratio,
    # heavy dilution, shrinking gross margin and asset turnover.
    current = _fy(
        net_income=-10.0,
        operating_cash_flow=-20.0,
        total_assets=1100.0,
        current_assets=300.0,
        current_liabilities=280.0,
        long_term_debt=400.0,
        gross_profit=400.0,
        revenue=1000.0,
        shares_outstanding=130.0,
    )

    result = compute_piotroski(current, prior)

    assert result.score == 0
    assert all(v is False for v in result.signals.values())


def test_missing_prior_year_data_yields_none_signals() -> None:
    prior = _fy(long_term_debt=None, current_assets=None)
    current = _fy()

    result = compute_piotroski(current, prior)

    assert result.signals["leverage_decreasing"] is None
    assert result.signals["current_ratio_improving"] is None
    # signals with fully-known inputs still compute
    assert result.signals["positive_cfo"] is True
