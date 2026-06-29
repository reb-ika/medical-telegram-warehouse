"""
scripts/load_to_postgres.py

Raw Data Loader: JSON Data Lake → PostgreSQL
--------------------------------------------
Reads all scraped JSON files from data/raw/telegram_messages/
and loads them into a PostgreSQL table called raw.telegram_messages.

This is the "Load" step in our ELT pipeline.
After this, dbt handles the "Transform" step inside the database.
"""

import json
import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ─── Load environment variables ──────────────────────────────────────────────
load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "medical_warehouse")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

# SQLAlchemy connection string for PostgreSQL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ─── Logging setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/loader.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ─── Read all JSON files from the data lake ──────────────────────────────────
def read_all_json_files() -> pd.DataFrame:
    """
    Walks through data/raw/telegram_messages/ recursively,
    reads every .json file, and combines them into one DataFrame.

    Each JSON file is a list of message records.
    We read them chunk by chunk to avoid loading everything into RAM at once.
    """
    data_lake_path = Path("data/raw/telegram_messages")
    all_records = []

    json_files = list(data_lake_path.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files to load")

    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                records = json.load(f)
                # records is a list of message dicts
                all_records.extend(records)
                logger.info(f"  Read {len(records)} records from {filepath}")
        except Exception as e:
            logger.error(f"  Failed to read {filepath}: {e}")

    logger.info(f"Total records loaded from data lake: {len(all_records)}")
    return pd.DataFrame(all_records)


# ─── Clean the DataFrame before loading ──────────────────────────────────────
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Basic cleaning before pushing to PostgreSQL:
    - Parse message_date as proper datetime
    - Fill missing text with empty string
    - Ensure numeric columns are integers
    - Drop exact duplicate rows
    """
    # Convert date string to actual datetime (PostgreSQL needs proper types)
    df["message_date"] = pd.to_datetime(df["message_date"], utc=True, errors="coerce")

    # Fill missing text
    df["message_text"] = df["message_text"].fillna("")

    # Fill missing numeric fields with 0
    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0).astype(int)
    df["forwards"] = pd.to_numeric(df["forwards"], errors="coerce").fillna(0).astype(int)

    # Fill missing booleans
    df["has_media"] = df["has_media"].fillna(False).astype(bool)

    # Drop duplicates (same message_id + channel_name)
    before = len(df)
    df = df.drop_duplicates(subset=["message_id", "channel_name"])
    after = len(df)
    logger.info(f"Removed {before - after} duplicate records")

    return df


# ─── Load DataFrame to PostgreSQL ────────────────────────────────────────────
def load_to_postgres(df: pd.DataFrame, engine):
    with engine.connect() as conn:
        # Create the raw schema if it doesn't exist
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        # DROP with CASCADE handles the dbt view dependency
        conn.execute(text("DROP TABLE IF EXISTS raw.telegram_messages CASCADE;"))
        conn.commit()
        logger.info("Schema 'raw' ready")

    # Write to PostgreSQL
    df.to_sql(
        name="telegram_messages",
        schema="raw",
        con=engine,
        if_exists="append",    # table already dropped above, so append is safe
        index=False,
        chunksize=500,
    )
    logger.info(f"Loaded {len(df)} rows into raw.telegram_messages")

# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("Starting: JSON Data Lake → PostgreSQL Loader")
    logger.info("=" * 60)

    # Step 1: Read all JSON files
    df = read_all_json_files()

    if df.empty:
        logger.error("No data found! Make sure the scraper ran successfully.")
        return

    # Step 2: Clean the data
    df = clean_dataframe(df)
    logger.info(f"Cleaned DataFrame shape: {df.shape}")
    logger.info(f"Columns: {list(df.columns)}")

    # Step 3: Connect to PostgreSQL
    logger.info(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME}")
    engine = create_engine(DATABASE_URL)

    # Step 4: Load to PostgreSQL
    load_to_postgres(df, engine)

    # Step 5: Verify — count rows in the table
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.telegram_messages"))
        count = result.scalar()
        logger.info(f"Verification: {count} rows in raw.telegram_messages ✓")

    logger.info("Done! Data is in PostgreSQL, ready for dbt.")


if __name__ == "__main__":
    main()