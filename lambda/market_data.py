"""Replace get_quote(symbol) to use another vendor; keep the Quote contract."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from urllib.parse import quote
from http_client import request_json


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    previous_close: float
    as_of: datetime

    @property
    def change(self):
        return self.price - self.previous_close

    @property
    def change_percent(self):
        return self.change / self.previous_close * 100


def parse_quote(symbol, data):
    try:
        chart = data["chart"]
        if chart.get("error"):
            raise ValueError()
        meta = chart["result"][0]["meta"]
        if meta["symbol"] != symbol or meta["currency"] != "JPY":
            raise ValueError()
        price = float(meta["regularMarketPrice"])
        # range=1d: chartPreviousClose is the preceding session close.
        previous = float(meta["chartPreviousClose"])
        timestamp = float(meta["regularMarketTime"])
        if not all(math.isfinite(v) and v > 0 for v in (price, previous, timestamp)):
            raise ValueError()
        return Quote(symbol, price, previous, datetime.fromtimestamp(timestamp, timezone.utc))
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError):
        raise RuntimeError(f"Invalid market data: {symbol}") from None


def get_quote(symbol):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + quote(symbol, safe="") + "?range=1d&interval=1m")
    return parse_quote(symbol, request_json(url, {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}))
