import pandas as pd
from ftplib import FTP
import io
import os

# Set working directory locally
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def fetch_nyse_tickers():
    print("[!] Connecting to Nasdaq FTP...")
    # Anonymous Nasdaq FTP server
    ftp = FTP("ftp.nasdaqtrader.com")
    ftp.login()

    print("[!] Downloading ticker list...")
    mem_file = io.BytesIO()
    # File contains NYSE stocks
    ftp.retrbinary("RETR SymbolDirectory/otherlisted.txt", mem_file.write)
    ftp.quit()

    mem_file.seek(0)
    print("[!] Processing data with Pandas...")

    # Pipe-separated file
    df = pd.read_csv(mem_file, sep="|")

    # Drop invalid EOF row
    df = df.dropna(subset=["Exchange"])

    # Filter NYSE only
    # Drop test issues
    nyse_df = df[(df["Exchange"] == "N") & (df["Test Issue"] == "N")]

    # Convert to list
    tickers = nyse_df["ACT Symbol"].astype(str).tolist()

    # Drop preferred/class stocks
    clean_tickers = [t for t in tickers if not ("$" in t or "." in t)]

    # Save to CSV
    output_df = pd.DataFrame({"Ticker": clean_tickers})
    output_df.to_csv("nyse_tickers.csv", index=False)

    print(
        f"✅ BINGO! {len(clean_tickers)} clean NYSE tickers saved to 'nyse_tickers.csv'."
    )


if __name__ == "__main__":
    fetch_nyse_tickers()
