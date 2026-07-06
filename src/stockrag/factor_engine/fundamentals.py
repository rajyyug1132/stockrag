from dataclasses import dataclass


@dataclass(frozen=True)
class FiscalYearFundamentals:
    """One fiscal year of statement data, as reported on a 10-K.

    Any field may be ``None`` when the filer didn't use (or later stopped
    using) the corresponding XBRL tag family.
    """

    fiscal_year_end: str
    revenue: float | None
    cost_of_revenue: float | None
    gross_profit: float | None
    net_income: float | None
    operating_cash_flow: float | None
    capex: float | None
    total_assets: float | None
    current_assets: float | None
    total_liabilities: float | None
    current_liabilities: float | None
    long_term_debt: float | None
    stockholders_equity: float | None
    shares_outstanding: float | None
