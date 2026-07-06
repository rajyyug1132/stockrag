from datetime import datetime
from dataclasses import dataclass

from stockrag.config import settings
from stockrag.edgar.client import EdgarClient
from stockrag.factor_engine.fundamentals import FiscalYearFundamentals

# Priority-ordered XBRL tag fallbacks: filers use different tags for the same
# concept (and sometimes switch tags across years), so we try each in order
# and use the first tag that has any annual (10-K, FY) data at all.
FUNDAMENTAL_TAGS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ],
    "gross_profit": ["GrossProfit"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "total_liabilities": ["Liabilities"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": ["LongTermDebtNoncurrent"],
    "stockholders_equity": ["StockholdersEquity"],
}

SHARES_TAGS = ["EntityCommonStockSharesOutstanding"]

# EntityCommonStockSharesOutstanding is a dei "cover page" fact dated at
# filing time, not at fiscal year end, so it can't be matched by exact date
# like the us-gaap statement tags. Large accelerated filers must file a 10-K
# within 60 days of fiscal year end, so a generous window still excludes
# unrelated periods.
SHARES_MATCH_TOLERANCE_DAYS = 75


@dataclass(frozen=True)
class _FactPoint:
    val: float
    filed: str


def _nearest_point(series: dict[str, "_FactPoint"], target_end: str, max_days: int) -> "_FactPoint | None":
    if not series:
        return None
    target_date = datetime.strptime(target_end, "%Y-%m-%d").date()
    best: tuple[int, _FactPoint] | None = None
    for end, point in series.items():
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
        delta = abs((end_date - target_date).days)
        if delta > max_days:
            continue
        if best is None or delta < best[0]:
            best = (delta, point)
    return best[1] if best else None


def _annual_series(taxonomy_facts: dict, tags: list[str]) -> dict[str, _FactPoint]:
    """Best value per fiscal-year-end for the first tag (in priority order)
    that has any 10-K/FY data, deduped by ``end`` date keeping the latest
    ``filed`` (later filings may restate a prior year's figure).
    """
    for tag in tags:
        node = taxonomy_facts.get(tag)
        if not node:
            continue
        series: dict[str, _FactPoint] = {}
        for unit_values in node.get("units", {}).values():
            for item in unit_values:
                if item.get("form") != "10-K" or item.get("fp") != "FY":
                    continue
                end = item.get("end")
                val = item.get("val")
                filed = item.get("filed")
                if end is None or val is None or filed is None:
                    continue
                existing = series.get(end)
                if existing is None or filed > existing.filed:
                    series[end] = _FactPoint(val=float(val), filed=filed)
        if series:
            return series
    return {}


def companyfacts_url(cik: int) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def fundamentals_from_companyfacts(data: dict) -> list[FiscalYearFundamentals]:
    """Parse a companyfacts JSON payload into per-fiscal-year fundamentals,
    sorted oldest to newest, keeping every fiscal year end reported by any
    tracked tag (fields for years with partial coverage are left ``None``).
    """
    gaap = data.get("facts", {}).get("us-gaap", {})
    dei = data.get("facts", {}).get("dei", {})

    field_series = {field: _annual_series(gaap, tags) for field, tags in FUNDAMENTAL_TAGS.items()}
    shares_series = _annual_series(dei, SHARES_TAGS)

    # Fiscal years are defined by the us-gaap statement tags only; shares
    # outstanding is matched to the nearest cover-page date below, since its
    # own "end" date is the filing date, not the fiscal year end.
    all_ends = sorted(set().union(*(s.keys() for s in field_series.values())))

    def value(field: str, end: str) -> float | None:
        point = field_series[field].get(end)
        return point.val if point else None

    years: list[FiscalYearFundamentals] = []
    for end in all_ends:
        gross_profit = value("gross_profit", end)
        if gross_profit is None:
            revenue = value("revenue", end)
            cost = value("cost_of_revenue", end)
            if revenue is not None and cost is not None:
                gross_profit = revenue - cost

        shares_point = _nearest_point(shares_series, end, max_days=SHARES_MATCH_TOLERANCE_DAYS)
        years.append(
            FiscalYearFundamentals(
                fiscal_year_end=end,
                revenue=value("revenue", end),
                cost_of_revenue=value("cost_of_revenue", end),
                gross_profit=gross_profit,
                net_income=value("net_income", end),
                operating_cash_flow=value("operating_cash_flow", end),
                capex=value("capex", end),
                total_assets=value("total_assets", end),
                current_assets=value("current_assets", end),
                total_liabilities=value("total_liabilities", end),
                current_liabilities=value("current_liabilities", end),
                long_term_debt=value("long_term_debt", end),
                stockholders_equity=value("stockholders_equity", end),
                shares_outstanding=shares_point.val if shares_point else None,
            )
        )
    return years


def get_annual_fundamentals(cik: int, client: EdgarClient) -> list[FiscalYearFundamentals]:
    cache_path = settings.facts_dir / f"CIK{cik:010d}.json"
    data = client.get_json(companyfacts_url(cik), cache_path=cache_path)
    return fundamentals_from_companyfacts(data)
