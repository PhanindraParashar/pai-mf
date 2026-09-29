"""Keep current AMFI quote metadata separate from historical NAV prices."""

from paimf.providers import MarketData


def main() -> None:
    data = MarketData()
    scheme_codes = ["122639", "118989"]

    # mftool's bulk endpoint returns current quote details. Columns reflect
    # the upstream response, so inspect them instead of assuming a fixed shape.
    quotes = data.quotes_frame(scheme_codes, show_progress=False)
    print("Quote columns:", quotes.columns.tolist())
    print(quotes.head())

    # Historical NAV has the standard date/price columns for rolling analysis.
    nav = data.get_history("amfi:122639", years=1)
    print("\nLatest historical NAV observations:")
    print(nav.tail())

    # Check the scheme's plan and share class before comparing its NAV to an index.


if __name__ == "__main__":
    main()
