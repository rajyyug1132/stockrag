from stockrag.edgar.companyfacts import companyfacts_url, fundamentals_from_companyfacts


def _usd_facts(concept: str, points: list[dict]) -> dict:
    return {concept: {"units": {"USD": points}}}


def test_tag_fallback_and_gross_profit_derivation() -> None:
    # This filer never reports "GrossProfit" directly, and uses the
    # secondary "Revenues" tag rather than the priority "RevenueFromContract..." tag.
    data = {
        "facts": {
            "us-gaap": {
                **_usd_facts(
                    "Revenues",
                    [
                        {"end": "2022-12-31", "val": 900, "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-01"},
                        {"end": "2023-12-31", "val": 1000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                    ],
                ),
                **_usd_facts(
                    "CostOfRevenue",
                    [
                        {"end": "2022-12-31", "val": 450, "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-01"},
                        {"end": "2023-12-31", "val": 500, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                    ],
                ),
                **_usd_facts(
                    "NetIncomeLoss",
                    [
                        {"end": "2022-12-31", "val": 80, "fy": 2022, "fp": "FY", "form": "10-K", "filed": "2023-02-01"},
                        {"end": "2023-12-31", "val": 100, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                        # A 10-Q data point for the same concept must be ignored.
                        {"end": "2023-09-30", "val": 999, "fy": 2023, "fp": "Q3", "form": "10-Q", "filed": "2023-11-01"},
                    ],
                ),
            },
            "dei": {},
        }
    }

    years = fundamentals_from_companyfacts(data)

    assert [y.fiscal_year_end for y in years] == ["2022-12-31", "2023-12-31"]
    fy2023 = years[1]
    assert fy2023.revenue == 1000
    assert fy2023.cost_of_revenue == 500
    assert fy2023.gross_profit == 1000 - 500  # derived, since GrossProfit tag absent
    assert fy2023.net_income == 100  # 10-Q point excluded


def test_restatement_keeps_latest_filed_value() -> None:
    data = {
        "facts": {
            "us-gaap": _usd_facts(
                "NetIncomeLoss",
                [
                    {"end": "2023-12-31", "val": 100, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                    # Restated in a later filing - should win over the earlier value.
                    {"end": "2023-12-31", "val": 95, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-08-01"},
                ],
            ),
            "dei": {},
        }
    }

    years = fundamentals_from_companyfacts(data)

    assert len(years) == 1
    assert years[0].net_income == 95


def test_companyfacts_url_zero_pads_cik() -> None:
    assert companyfacts_url(320193) == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
