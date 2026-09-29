"""Optional market data integrations.

Importing this module requires only pandas. ``mftool`` and ``yfinance`` are
loaded on demand when their respective providers first fetch data.
"""

from .amfi import AmfiProvider
from .market import MarketData
from .yahoo import YahooFinanceProvider

__all__ = ["AmfiProvider", "MarketData", "YahooFinanceProvider"]
