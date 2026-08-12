"""
openfda_client.py
------------------
Thin client around the openFDA /drug/event.json endpoint.

Handles:
- authenticated vs. unauthenticated requests
- the two different response shapes openFDA returns (a plain results-count
  query vs. an aggregated `count=` query)
- polite rate limiting (sleep between calls)
- quarter-range generation for the extraction loop

Reference: https://open.fda.gov/apis/drug/event/how-to-use-the-endpoint/
"""

from __future__ import annotations

import os
import time
import datetime as dt
from typing import Optional

import requests

BASE_URL = "https://api.fda.gov/drug/event.json"

# openFDA rate limits (see https://open.fda.gov/apis/authentication):
#   without a key: 1,000 requests/day,   40 requests/minute
#   with a key:  120,000 requests/day,  240 requests/minute
DEFAULT_SLEEP_NO_KEY = 1.6   # seconds between calls, safely under 40/min
DEFAULT_SLEEP_WITH_KEY = 0.3  # seconds between calls, safely under 240/min


class OpenFDAClient:
    def __init__(self, api_key: Optional[str] = None, sleep: Optional[float] = None):
        self.api_key = api_key or os.environ.get("OPENFDA_API_KEY") or None
        if sleep is not None:
            self.sleep = sleep
        else:
            self.sleep = DEFAULT_SLEEP_WITH_KEY if self.api_key else DEFAULT_SLEEP_NO_KEY

    def _get(self, params: dict) -> dict:
        if self.api_key:
            params = {"api_key": self.api_key, **params}
        resp = requests.get(BASE_URL, params=params, timeout=30)
        time.sleep(self.sleep)  # be a good API citizen
        if resp.status_code == 404:
            # openFDA returns 404 when a query matches zero records - this is
            # a valid "zero" answer, not an error.
            return {"results": [], "meta": {"results": {"total": 0}}}
        resp.raise_for_status()
        return resp.json()

    def get_count(self, search: str) -> int:
        """
        Return the total number of reports matching `search`.

        openFDA doesn't have a dedicated "just give me the total" mode, so we
        use the documented trick of aggregating on a field that only ever
        has 1-2 buckets (`serious`: 1=serious, 2=not serious) and summing the
        bucket counts. This avoids ever pulling full report bodies just to
        get a number, which keeps responses small and fast.
        """
        data = self._get({"search": search, "count": "serious"})
        results = data.get("results", [])
        return sum(item["count"] for item in results)

    def get_reaction_breakdown(self, search: str, limit: int = 500) -> dict:
        """
        Return {REACTION_TERM: count} for all reactions matching `search`,
        aggregated server-side via count=patient.reaction.reactionmeddrapt.exact.
        Used to fetch 'a' (drug+reaction+quarter) for every tracked reaction
        in a single API call per quarter instead of one call per reaction.
        """
        data = self._get({
            "search": search,
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": limit,
        })
        return {item["term"]: item["count"] for item in data.get("results", [])}

    def get_raw_reports(self, search: str, limit: int = 5) -> dict:
        """Return raw report records (used only for Day-1 exploration)."""
        return self._get({"search": search, "limit": limit})


def generate_quarter_ranges(start: str, end: str):
    """
    Yield (start_yyyymmdd, end_yyyymmdd, label) tuples for each calendar
    quarter between `start` and `end` (inclusive), where start/end are
    'YYYY-MM-DD' strings.

    label format: 'YYYYQn', matching FAERS' own quarterly reporting cadence.
    """
    start_date = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)

    quarter_starts = [(1, 1), (4, 1), (7, 1), (10, 1)]
    quarter_end_month = {1: 3, 4: 6, 7: 9, 10: 12}

    year = start_date.year
    results = []
    while True:
        for qmonth, qday in quarter_starts:
            q_start = dt.date(year, qmonth, qday)
            end_month = quarter_end_month[qmonth]
            if end_month == 12:
                q_end = dt.date(year, 12, 31)
            else:
                next_month_first = dt.date(year, end_month + 1, 1)
                q_end = next_month_first - dt.timedelta(days=1)

            if q_start > end_date:
                return results
            if q_end < start_date:
                continue

            quarter_num = qmonth // 3 + 1
            label = f"{year}Q{quarter_num}"
            results.append((q_start.strftime("%Y%m%d"), q_end.strftime("%Y%m%d"), label))
        year += 1


def build_drug_filter(generic_name: str = "semaglutide") -> str:
    """
    openFDA normalizes brand names (Ozempic, Wegovy, Rybelsus) to a single
    `openfda.generic_name` field, so filtering on generic_name captures all
    brand-name reports without an explicit OR clause across product names.
    """
    return f'patient.drug.openfda.generic_name:"{generic_name}"'


def build_date_filter(start_yyyymmdd: str, end_yyyymmdd: str) -> str:
    return f"receivedate:[{start_yyyymmdd} TO {end_yyyymmdd}]"
