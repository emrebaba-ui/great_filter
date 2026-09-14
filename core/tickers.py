import pandas as pd
from ftplib import FTP
import io

from config import *


def fetch_nyse_tickers():
    ftp = FTP("ftp.nasdaqtrader.com")
    ftp.login()

    mem_file = io.BytesIO()
    ftp.retrbinary("RETR SymbolDirectory/otherlisted.txt", mem_file.write)
    ftp.quit()

    mem_file.seek(0)

    # Pipe-separated file
    df = pd.read_csv(mem_file, sep="|")
    df = df.dropna(subset=["Exchange"])
    # NYSE in, Test Issue out
    nyse_df = df[(df["Exchange"] == "N") & (df["Test Issue"] == "N")]
    tickers = nyse_df["ACT Symbol"].astype(str).tolist()
    # Drop preferred/class
    clean_tickers = [t for t in tickers if not ("$" in t or "." in t)]

    output_df = pd.DataFrame({"Ticker": clean_tickers})
    output_df.to_csv(TICKERS_FILE, index=False)

    print(
        f"{len(clean_tickers)} clean NYSE tickers saved to '{TICKERS_FILE}'."
    )


if __name__ == "__main__":
    fetch_nyse_tickers()
