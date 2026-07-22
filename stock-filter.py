import yfinance as yf
import pandas as pd
from abc import ABC, abstractmethod
import time
import os

# Lock working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ==========================================
# 1. DATA MODEL
# ==========================================
class StockData:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.roi = None
        self.sales_growth = None
        self.profit_growth = None
        self.peg = None
        self.pe = None
        self.fcf_to_profit = None
        self.beta = None

        self.category = None
        self.note = ""
        self.is_valid = False
        self.fetch_error = ""  # Reason for missing data


class DataFetcher:
    @staticmethod
    def _calculate_cagr(series: pd.Series) -> float:
        series = series.dropna()
        if len(series) < 2:
            return None
        newest_val = series.iloc[0]
        oldest_val = series.iloc[-1]
        years = len(series) - 1
        if oldest_val <= 0 or newest_val <= 0:
            return None
        return ((newest_val / oldest_val) ** (1 / years)) - 1

    @staticmethod
    def fetch(ticker_sym: str) -> StockData:
        stock = StockData(ticker_sym)
        try:
            t = yf.Ticker(ticker_sym)
            info = t.info

            # Check if delisted/missing
            if not info or "symbol" not in info:
                stock.fetch_error = "Not found/Delisted"
                return stock

            financials = t.financials
            cashflow = t.cashflow

            stock.roi = info.get("returnOnEquity")
            stock.peg = info.get("pegRatio")
            stock.pe = info.get("trailingPE")
            stock.beta = info.get("beta")

            # Calc CAGR if data exists
            if financials is not None and not financials.empty:
                if "Total Revenue" in financials.index:
                    stock.sales_growth = DataFetcher._calculate_cagr(
                        financials.loc["Total Revenue"]
                    )
                if "Net Income" in financials.index:
                    stock.profit_growth = DataFetcher._calculate_cagr(
                        financials.loc["Net Income"]
                    )

            fcf = info.get("freeCashflow")
            net_income = info.get("netIncomeToCommon")

            # Calc FCF/Profit ratio
            if fcf is not None and net_income is not None and net_income > 0:
                stock.fcf_to_profit = fcf / net_income
            else:
                if (
                    cashflow is not None
                    and financials is not None
                    and not cashflow.empty
                    and not financials.empty
                ):
                    if (
                        "Free Cash Flow" in cashflow.index
                        and "Net Income" in financials.index
                    ):
                        fcf_series = cashflow.loc["Free Cash Flow"].dropna()
                        ni_series = financials.loc["Net Income"].dropna()
                        if not fcf_series.empty and not ni_series.empty:
                            recent_ni = ni_series.iloc[0]
                            if recent_ni > 0:
                                stock.fcf_to_profit = fcf_series.iloc[0] / recent_ni

            stock.is_valid = True
        except Exception:
            stock.fetch_error = "API Fetch Error"

        return stock


# ==========================================
# 2. STRATEGY PATTERN
# ==========================================
class FilterStrategy(ABC):
    @abstractmethod
    def evaluate(self, stock: StockData) -> tuple[bool, str]:
        pass


class AggressiveStrategy(FilterStrategy):
    def evaluate(self, s: StockData) -> tuple[bool, str]:
        if s.roi is None:
            return False, "Missing: ROI"
        if s.sales_growth is None:
            return False, "Missing: Sales Grw"
        if s.profit_growth is None:
            return False, "Missing: Profit Grw"
        if s.peg is None:
            return False, "Missing: PEG"
        if s.fcf_to_profit is None:
            return False, "Missing: FCF/Profit"

        if s.roi <= 0.20:
            return False, f"Low ROI ({s.roi*100:.1f}%)"
        if s.sales_growth <= 0.10:
            return False, f"Low Sales Grw ({s.sales_growth*100:.1f}%)"
        if s.profit_growth <= 0.20:
            return False, f"Low Profit Grw ({s.profit_growth*100:.1f}%)"
        if s.peg >= 3.0:
            return False, f"High PEG ({s.peg:.2f})"
        if s.fcf_to_profit <= 0.50:
            return False, f"Low FCF/Profit ({s.fcf_to_profit*100:.1f}%)"

        s.category = "Aggressive"
        s.note = "Expensive (PEG 2-3)" if s.peg >= 2.0 else "Suitable"
        return True, "Passed"


class ModerateStrategy(FilterStrategy):
    def evaluate(self, s: StockData) -> tuple[bool, str]:
        if s.roi is None:
            return False, "Missing: ROI"
        if s.profit_growth is None:
            return False, "Missing: Profit Grw"
        if s.peg is None:
            return False, "Missing: PEG"
        if s.pe is None:
            return False, "Missing: PE"
        if s.fcf_to_profit is None:
            return False, "Missing: FCF/Profit"
        if s.beta is None:
            return False, "Missing: Beta"

        if s.roi <= 0.10:
            return False, f"Low ROI ({s.roi*100:.1f}%)"
        if s.profit_growth <= 0.10:
            return False, f"Low Profit Grw ({s.profit_growth*100:.1f}%)"
        if s.peg >= 2.0:
            return False, f"High PEG ({s.peg:.2f})"
        if s.pe >= 20:
            return False, f"High PE ({s.pe:.2f})"
        if s.fcf_to_profit <= 0.50:
            return False, f"Low FCF/Profit ({s.fcf_to_profit*100:.1f}%)"
        if not (0.8 <= s.beta <= 1.2):
            return False, f"Bad Beta ({s.beta:.2f})"

        s.category = "Moderate"
        return True, "Passed"


class DefensiveStrategy(FilterStrategy):
    def evaluate(self, s: StockData) -> tuple[bool, str]:
        if s.sales_growth is None:
            return False, "Missing: Sales Grw"
        if s.pe is None:
            return False, "Missing: PE"
        if s.fcf_to_profit is None:
            return False, "Missing: FCF/Profit"
        if s.beta is None:
            return False, "Missing: Beta"

        if s.sales_growth < 0.0:
            return False, f"Neg Sales Grw ({s.sales_growth*100:.1f}%)"
        if s.pe >= 20:
            return False, f"High PE ({s.pe:.2f})"
        if s.fcf_to_profit <= 0.50:
            return False, f"Low FCF/Profit ({s.fcf_to_profit*100:.1f}%)"
        if s.beta >= 1.0:
            return False, f"High Beta ({s.beta:.2f})"

        s.category = "Defensive"
        return True, "Passed"


# ==========================================
# 3. SCREENER ENGINE
# ==========================================
class Screener:
    def __init__(self, tickers: list):
        self.tickers = tickers
        self.strategies = [
            AggressiveStrategy(),
            ModerateStrategy(),
            DefensiveStrategy(),
        ]
        self.results = []

    def run(self):
        print(f"\n[!] Scanning {len(self.tickers)} stocks. X-Ray Mode Active...\n")
        print("-" * 80)

        for i, ticker in enumerate(self.tickers, 1):
            print(
                f"[{i:04d}/{len(self.tickers):04d}] {ticker.ljust(5)} ->",
                end=" ",
                flush=True,
            )

            stock = DataFetcher.fetch(ticker)
            if not stock.is_valid:
                print(f"❌ SKIPPED ({stock.fetch_error})")
                continue

            matched = False
            fail_reasons = []

            for strategy in self.strategies:
                passed, reason = strategy.evaluate(stock)
                if passed:
                    self.results.append(stock)
                    print(f"✅ BINGO! (Added to {stock.category})")
                    matched = True
                    break
                else:
                    # Log failure reasons
                    strat_name = strategy.__class__.__name__.replace("Strategy", "")
                    fail_reasons.append(f"{strat_name}: {reason}")

            if not matched:
                # Print aggressive rejection
                print(f"🗑️ REJECTED ({fail_reasons[0]})")

            # Anti-ban sleep
            time.sleep(0.5)

        print("-" * 80 + "\n")


# ==========================================
# 4. PRESENTATION LAYER
# ==========================================
class ReportGenerator:
    @staticmethod
    def show(results: list):
        if not results:
            print("Market is tough! No stocks passed your strict criteria.")
            return

        def fmt_pct(v):
            return f"{v*100:.1f}%" if v is not None else "N/A"

        def fmt_flt(v):
            return f"{v:.2f}" if v is not None else "N/A"

        data = []
        for s in results:
            data.append(
                {
                    "Ticker": s.ticker,
                    "Category": s.category,
                    "Note": s.note,
                    "ROI": fmt_pct(s.roi),
                    "Sales Grw": fmt_pct(s.sales_growth),
                    "Profit Grw": fmt_pct(s.profit_growth),
                    "PE": fmt_flt(s.pe),
                    "PEG": fmt_flt(s.peg),
                    "FCF/Profit": fmt_pct(s.fcf_to_profit),
                    "Beta": fmt_flt(s.beta),
                }
            )

        df = pd.DataFrame(data)
        print("=" * 110)
        print("STOCK SCREENER RESULTS".center(110))
        print("=" * 110)
        print(df.to_string(index=False))
        print("=" * 110)


# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        # Load ticker list
        df_tickers = pd.read_csv("nyse_tickers.csv")
        nyse_list = df_tickers["Ticker"].tolist()

        screener = Screener(nyse_list)
        screener.run()
        ReportGenerator.show(screener.results)

    except Exception as e:
        print(f"Execution Error: {e}")

    # Keep console open
    input("\n[+] Process completed. Press ENTER to exit...")
