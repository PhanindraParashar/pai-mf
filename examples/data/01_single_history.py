"""Fetch individual histories from Yahoo and AMFI through one interface."""

from paimf.providers import MarketData


def main() -> None:
    data = MarketData()

    # Familiar index aliases resolve to Yahoo symbols. NIFTY150 is this
    # library's short alias for the Nifty Midcap 150 index.
    print("Selected index aliases and Yahoo symbols:")
    for name in (
        "NIFTY50",
        "NIFTY150",
        "NIFTY500",
        "S&P500",
        "NASDAQ100",
        "DOWJONES",
        "FTSE100",
        "DAX",
        "NIKKEI225",
        "HANGSENG",
    ):
        print(f"  {name}: {data.INDEX_TICKERS[name]}")

    identifiers = {
        "Indian index": "NIFTY50",  # An index alias is routed automatically.
        "US stock": "yahoo:AAPL",
        "Indian mutual fund": "amfi:122639",
    }
    for label, identifier in identifiers.items():
        # Both sources return the same date/price shape for FundAnalysis. The
        # AMFI identifier is a scheme code, not a ticker or fund name.
        history = data.get_history(identifier, years=2)
        print(f"\n{label} ({identifier})")
        print(history.tail(2))
        print("Source metadata:", history.attrs)


if __name__ == "__main__":
    main()
