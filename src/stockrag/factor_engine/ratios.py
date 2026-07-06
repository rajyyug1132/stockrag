from stockrag.factor_engine.fundamentals import FiscalYearFundamentals


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def free_cash_flow(fy: FiscalYearFundamentals) -> float | None:
    if fy.operating_cash_flow is None or fy.capex is None:
        return None
    return fy.operating_cash_flow - fy.capex


def roe(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.net_income, fy.stockholders_equity)


def net_margin(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.net_income, fy.revenue)


def eps(fy: FiscalYearFundamentals) -> float | None:
    return safe_div(fy.net_income, fy.shares_outstanding)


def revenue_growth(current: FiscalYearFundamentals, prior: FiscalYearFundamentals) -> float | None:
    if current.revenue is None or prior.revenue is None:
        return None
    return safe_div(current.revenue - prior.revenue, prior.revenue)


def pe_ratio(price: float | None, eps_value: float | None) -> float | None:
    return safe_div(price, eps_value)


def p_fcf_ratio(market_cap: float | None, fcf: float | None) -> float | None:
    return safe_div(market_cap, fcf)
