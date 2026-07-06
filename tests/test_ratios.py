from stockrag.factor_engine.fundamentals import FiscalYearFundamentals
from stockrag.factor_engine.ratios import (
    eps,
    free_cash_flow,
    net_margin,
    p_fcf_ratio,
    pe_ratio,
    revenue_growth,
    roe,
    safe_div,
)


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


def test_safe_div_handles_none_and_zero() -> None:
    assert safe_div(10.0, 2.0) == 5.0
    assert safe_div(None, 2.0) is None
    assert safe_div(10.0, None) is None
    assert safe_div(10.0, 0.0) is None


def test_basic_ratios() -> None:
    fy = _fy()
    assert roe(fy) == 100.0 / 500.0
    assert net_margin(fy) == 100.0 / 1000.0
    assert eps(fy) == 100.0 / 100.0
    assert free_cash_flow(fy) == 130.0 - 50.0


def test_revenue_growth() -> None:
    prior = _fy(revenue=800.0)
    current = _fy(revenue=1000.0)
    assert revenue_growth(current, prior) == (1000.0 - 800.0) / 800.0


def test_pe_and_p_fcf_ratio() -> None:
    fy = _fy()
    assert pe_ratio(price=50.0, eps_value=eps(fy)) == 50.0 / 1.0
    fcf = free_cash_flow(fy)
    assert p_fcf_ratio(market_cap=5000.0, fcf=fcf) == 5000.0 / fcf


def test_missing_fields_propagate_none() -> None:
    fy = _fy(net_income=None)
    assert roe(fy) is None
    assert net_margin(fy) is None
    assert eps(fy) is None
