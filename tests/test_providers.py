"""Provider contracts without external network requests."""

from __future__ import annotations

import sys

import pandas as pd
import pytest

from paimf.providers import AmfiProvider, MarketData, YahooFinanceProvider


class FakeYahoo:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls: list[tuple[str, dict]] = []

    def download(self, symbol: str, **kwargs) -> pd.DataFrame:
        self.calls.append((symbol, kwargs))
        return self.frame.copy()


class FakeMftool:
    def __init__(self) -> None:
        self.history_calls: list[str] = []
        self.quote_calls: list[tuple[list[str], int, bool]] = []
        self.cache_enabled = True
        self.cache_cleared = False

    def get_scheme_historical_nav(self, code: str, *, as_Dataframe: bool) -> pd.DataFrame:
        assert as_Dataframe is True
        self.history_calls.append(code)
        if code == "404":
            raise ConnectionError("unavailable")
        return pd.DataFrame(
            {"nav": ["102", "101", "99", "not-a-number"]},
            index=pd.Index(
                ["02-01-2024", "01-01-2024", "01-01-2024", "31-12-2023"],
                name="date",
            ),
        )

    def get_bulk_quotes(self, codes: list[str], *, max_workers: int, show_progress: bool):
        self.quote_calls.append((codes, max_workers, show_progress))
        return {code: {"nav": "102"} if code != "404" else None for code in codes}

    def get_cache_stats(self):
        return {"hits": 1}

    def clear_cache(self):
        self.cache_cleared = True

    def disable_cache(self):
        self.cache_enabled = False

    def enable_cache(self):
        self.cache_enabled = True


def yahoo_frame() -> pd.DataFrame:
    columns = pd.MultiIndex.from_tuples([("Close", "^NSEI"), ("Adj Close", "^NSEI")])
    return pd.DataFrame(
        [[100, 98], [102, 99], [103, 101]],
        columns=columns,
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-01", "2024-01-02"], name="Date"),
    )


def test_yahoo_alias_raw_symbol_normalization_and_copy() -> None:
    client = FakeYahoo(yahoo_frame())
    provider = YahooFinanceProvider(client=client)
    history = provider.get_index("NIFTY 50", years=2)

    assert client.calls[0][0] == "^NSEI"
    assert client.calls[0][1]["auto_adjust"] is False
    assert client.calls[0][1]["threads"] is False
    assert history.columns.tolist() == ["date", "price"]
    assert history["date"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert history["price"].tolist() == [99, 101]

    history.loc[0, "price"] = -1
    assert provider.get_ticker("NIFTY50", years=2).loc[0, "price"] == 99
    assert len(client.calls) == 1

    provider.get_index("TCS.NS")
    assert client.calls[-1][0] == "TCS.NS"


def test_yahoo_date_range_and_batch_alias_deduplication() -> None:
    client = FakeYahoo(yahoo_frame())
    provider = YahooFinanceProvider(client=client)
    frames = provider.get_indices(["NIFTY50", "NIFTY 50", "^GSPC"], max_workers=2)
    assert list(frames) == ["NIFTY50", "^GSPC"]
    assert len(client.calls) == 2

    provider.get_ticker("ABC", start="2020-01-01", end="2021-01-01")
    assert client.calls[-1][1]["start"] == pd.Timestamp("2020-01-01")
    assert client.calls[-1][1]["end"] == pd.Timestamp("2021-01-01")
    with pytest.raises(ValueError, match="start must be before end"):
        provider.get_ticker("ABC", start="2021-01-01", end="2020-01-01")


def test_yahoo_handles_single_level_close_and_bad_data() -> None:
    frame = pd.DataFrame({"Close": [10.0, 11.0]}, index=pd.date_range("2024-01-01", periods=2))
    provider = YahooFinanceProvider(client=FakeYahoo(frame))
    assert provider.get_ticker("ABC")["price"].tolist() == [10.0, 11.0]

    malformed = YahooFinanceProvider(client=FakeYahoo(frame.rename(columns={"Close": "Other"})))
    with pytest.raises(ValueError, match="no Adj Close or Close"):
        malformed.get_ticker("ABC")


def test_amfi_nav_batch_quotes_bundle_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("paimf.providers._common.time.sleep", lambda _: None)
    client = FakeMftool()
    provider = AmfiProvider(client=client, max_workers=3)

    history = provider.get_mutual_fund(123)
    assert history["date"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert history["price"].tolist() == [99, 102]
    history.loc[0, "price"] = -1
    assert provider.get_mutual_fund("123").loc[0, "price"] == 99
    assert client.history_calls == ["123"]

    histories, failures = provider.get_mutual_funds([123, "404", 123], return_failures=True)
    assert list(histories) == ["123"]
    assert list(failures) == ["404"]
    assert provider.failed_histories == failures

    quotes = provider.quotes_frame([123, "404"], show_progress=False)
    assert quotes["scheme_code"].tolist() == ["123"]
    assert client.quote_calls[-1] == (["123", "404"], 2, False)
    bundle_quotes, bundle_histories = provider.get_mutual_fund_bundle([123])
    assert bundle_quotes["scheme_code"].tolist() == ["123"]
    assert list(bundle_histories) == ["123"]

    assert provider.mf_cache_stats() == {"hits": 1}
    provider.disable_mf_cache()
    assert client.cache_enabled is False
    provider.enable_mf_cache()
    assert client.cache_enabled is True
    provider.clear_mf_cache()
    assert client.cache_cleared is True
    provider.get_mutual_fund("123")
    assert client.history_calls == ["123", "404", "404", "404", "123"]


def test_amfi_batch_error_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("paimf.providers._common.time.sleep", lambda _: None)
    provider = AmfiProvider(client=FakeMftool())
    with pytest.raises(RuntimeError, match="unavailable"):
        provider.get_mutual_funds(["404"], errors="raise")
    with pytest.raises(ValueError, match="errors must be"):
        provider.get_mutual_funds(["123"], errors="ignore")


def test_optional_clients_load_only_when_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "mftool", None)
    monkeypatch.setitem(sys.modules, "yfinance", None)
    data = MarketData()
    assert data.benchmarks == {}
    assert data.get_mutual_funds([]) == {}
    assert data.get_indices([]) == {}

    with pytest.raises(ImportError, match=r"pai-mf\[amfi\]"):
        data.get_mutual_fund("123")
    with pytest.raises(ImportError, match=r"pai-mf\[yahoo\]"):
        data.get_ticker("ABC")


def test_market_data_facade_works_with_injected_clients() -> None:
    client = FakeMftool()
    yahoo = FakeYahoo(yahoo_frame())
    data = MarketData(mf=client, yahoo=yahoo)
    assert data.get_index("S&P 500")["price"].tolist() == [99, 101]
    assert yahoo.calls[0][0] == "^GSPC"
    assert data.get_mutual_fund("123")["price"].tolist() == [99, 102]
    assert data.mf is client


def test_single_identifier_and_invalid_prices_are_handled() -> None:
    data = MarketData(mf=FakeMftool(), yahoo=FakeYahoo(yahoo_frame()))
    assert list(data.get_indices("NIFTY50")) == ["NIFTY50"]
    assert list(data.get_mutual_funds("123")) == ["123"]

    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "nav": [100, float("inf"), -1],
        }
    )
    clean = data.normalize_price_frame(frame, "date", "nav")
    assert clean["price"].tolist() == [100]


def test_unified_history_routes_both_sources_and_keeps_metadata() -> None:
    amfi = FakeMftool()
    yahoo = FakeYahoo(yahoo_frame())
    data = MarketData(mf=amfi, yahoo=yahoo)

    fund = data.get_history(123, start="2024-01-01", end="2024-01-02")
    assert fund.columns.tolist() == ["date", "price"]
    assert fund["price"].tolist() == [99]
    assert fund.attrs == {"source": "amfi", "identifier": "123", "symbol": None}
    assert amfi.history_calls == ["123"]

    index = data.get_history("index:S&P 500")
    assert index["price"].tolist() == [99, 101]
    assert index.attrs == {"source": "yahoo", "identifier": "S&P500", "symbol": "^GSPC"}
    assert yahoo.calls[0][0] == "^GSPC"

    stock = data.get_history("yahoo:AAPL")
    assert stock.attrs == {"source": "yahoo", "identifier": "AAPL", "symbol": "AAPL"}
    assert yahoo.calls[-1][0] == "AAPL"
    assert data.get_history("123", source="yahoo").attrs["source"] == "yahoo"
    assert yahoo.calls[-1][0] == "123"


def test_unified_batch_labels_deduplication_and_failure_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("paimf.providers._common.time.sleep", lambda _: None)
    amfi = FakeMftool()
    yahoo = FakeYahoo(yahoo_frame())
    data = MarketData(mf=amfi, yahoo=yahoo, max_workers=3)

    histories, failures = data.get_histories(
        {"Fund": "amfi:123", "Index": "NIFTY50", "Same index": "NIFTY 50", "Missing": 404},
        errors="skip",
        return_failures=True,
    )
    assert list(histories) == ["Fund", "Index", "Same index"]
    assert list(failures) == ["Missing"]
    assert "unavailable" in failures["Missing"]
    assert len(yahoo.calls) == 1
    assert yahoo.calls[0][0] == "^NSEI"
    assert histories["Index"].attrs["symbol"] == "^NSEI"
    histories["Index"].loc[0, "price"] = -1
    assert histories["Same index"].loc[0, "price"] == 99

    assert list(data.get_histories([123, "123", "NIFTY50"])) == ["123", "NIFTY50"]
    assert data.get_histories([]) == {}
    with pytest.raises(RuntimeError, match="unavailable"):
        data.get_histories([404])


def test_unified_history_validates_requests_before_fetching() -> None:
    data = MarketData(mf=FakeMftool(), yahoo=FakeYahoo(yahoo_frame()))
    with pytest.raises(ValueError, match="source must be"):
        data.get_history("AAPL", source="other")
    with pytest.raises(ValueError, match="conflicts"):
        data.get_history("amfi:123", source="yahoo")
    with pytest.raises(ValueError, match="Unknown source prefix"):
        data.get_history("other:AAPL")
    with pytest.raises(ValueError, match="Unknown index alias"):
        data.get_history("index:unknown")
    with pytest.raises(ValueError, match="numeric scheme codes"):
        data.get_history("amfi:abc")
    with pytest.raises(ValueError, match="only interval"):
        data.get_history(123, interval="1wk")
    with pytest.raises(ValueError, match="before end"):
        data.get_history(123, start="2024-02-01", end="2024-01-01")
    with pytest.raises(RuntimeError, match="requested period"):
        data.get_history(123, start="2025-01-01", end="2025-02-01")
    with pytest.raises(ValueError, match="Duplicate history label"):
        data.get_histories({123: 123, "123": 123})


def test_common_index_aliases_resolve_to_expected_yahoo_symbols() -> None:
    provider = YahooFinanceProvider(client=FakeYahoo(yahoo_frame()))
    expected = {
        "NIFTY 50": ("NIFTY50", "^NSEI"),
        "Nifty Midcap 150": ("NIFTY150", "NIFTYMIDCAP150.NS"),
        "NIFTY500": ("NIFTY500", "^CRSLDX"),
        "S&P 500": ("S&P500", "^GSPC"),
        "NASDAQ-100": ("NASDAQ100", "^NDX"),
        "Dow Jones": ("DOWJONES", "^DJI"),
        "FTSE 100": ("FTSE100", "^FTSE"),
        "DAX": ("DAX", "^GDAXI"),
        "Nikkei 225": ("NIKKEI225", "^N225"),
        "Hang Seng": ("HANGSENG", "^HSI"),
    }
    for alias, resolved in expected.items():
        assert provider._canonical_index(alias) == resolved
