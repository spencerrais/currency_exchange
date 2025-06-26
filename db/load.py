import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os


def batched_execute_values(cur, query, rows, batch_size=1000):
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        execute_values(cur, query, batch)


def load_csv_to_postgres():
    conn = psycopg2.connect(
        dbname=os.environ.get("RDS_NAME"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
        host=os.environ.get("RDS_HOST"),
        port=os.environ.get("RDS_PORT"),
    )
    cur = conn.cursor()

    df = pd.read_csv("/tmp/kaggle_data/daily_forex_rates.csv", parse_dates=["date"])

    currencies = (
        df[["currency", "currency_name"]]
        .dropna(subset=["currency"])
        .drop_duplicates()
        .values.tolist()
    )

    execute_values(
        cur,
        """
        INSERT INTO currency (currency_symbol, currency_name)
        VALUES %s
        ON CONFLICT (currency_symbol) DO NOTHING
        """,
        currencies,
    )
    conn.commit()
    print("Currencies loaded successfully into PostgreSQL database.")

    rows = [
        (
            row["currency"],
            row["date"].date(),
            row["exchange_rate"],
        )
        for _, row in df.iterrows()
        if pd.notna(row["currency"]) and pd.notna(row["exchange_rate"])
    ]
    batched_execute_values(
        cur,
        """
        INSERT INTO exchange_rates (currency_symbol, rate_date, exchange_rate)
        VALUES %s
        ON CONFLICT (currency_symbol, rate_date) DO NOTHING
        """,
        rows,
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Exchange Rates loaded successfully into PostgreSQL database.")
