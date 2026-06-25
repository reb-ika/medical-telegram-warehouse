"""
scripts/load_yolo_to_postgres.py

Loads YOLO detection results CSV into PostgreSQL
as raw.yolo_detections table, ready for dbt to pick up.
"""

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5433")
DB_NAME = os.getenv("POSTGRES_DB", "medical_warehouse")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/load_yolo.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Loading YOLO detections CSV into PostgreSQL...")

    csv_path = Path("data/yolo_detections.csv")
    if not csv_path.exists():
        logger.error("data/yolo_detections.csv not found! Run yolo_detect.py first.")
        return

    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info(f"Read {len(df)} rows from CSV")

    # Cast types
    df["message_id"] = pd.to_numeric(df["message_id"], errors="coerce")
    df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce")
    df["channel_name"] = df["channel_name"].str.strip()

    # Connect and load
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        conn.commit()

    df.to_sql(
        name="yolo_detections",
        schema="raw",
        con=engine,
        if_exists="replace",
        index=False,
        chunksize=500,
    )
    logger.info(f"Loaded {len(df)} rows into raw.yolo_detections")

    # Verify
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM raw.yolo_detections")).scalar()
        cats = conn.execute(text("""
            SELECT image_category, COUNT(*) as total
            FROM raw.yolo_detections
            GROUP BY image_category
            ORDER BY total DESC
        """)).fetchall()

    logger.info(f"Verification: {count} rows in raw.yolo_detections")
    logger.info("Category breakdown:")
    for row in cats:
        logger.info(f"  {row[0]}: {row[1]}")

    logger.info("Done!")


if __name__ == "__main__":
    main()