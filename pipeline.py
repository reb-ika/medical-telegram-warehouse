"""
pipeline.py

Dagster Pipeline Orchestration for Medical Telegram Data Warehouse
------------------------------------------------------------------
Dagster turns our collection of scripts into a proper production pipeline.

Key concepts:
  - op       = one unit of work (like a function)
  - job      = a collection of ops wired together in order
  - schedule = runs the job automatically on a timer

Our pipeline runs in this order:
  1. scrape_telegram_data     → runs the Telegram scraper
  2. load_raw_to_postgres     → loads JSON files into PostgreSQL
  3. run_dbt_transformations  → runs dbt run + dbt test
  4. run_yolo_enrichment      → runs YOLO detection + loads to PostgreSQL
  5. run_dbt_final            → runs dbt again to build fct_image_detections

Run with:
  dagster dev -f pipeline.py
Then visit: http://localhost:3000
"""

import subprocess
import sys
from pathlib import Path

from dagster import (
    op,
    job,
    schedule,
    OpExecutionContext,
    ScheduleDefinition,
    Definitions,
    RunRequest,
)


# ── Helper: run a Python script as a subprocess ───────────────────────────────
def run_python_script(context: OpExecutionContext, script_path: str):
    """
    Runs a Python script using the same Python interpreter
    that's running Dagster (i.e. inside our venv).
    Streams output to Dagster logs line by line.
    """
    # Get the absolute path to the project root
    project_root = Path(__file__).parent.absolute()
    full_script_path = project_root / script_path

    context.log.info(f"Running: {full_script_path}")

    result = subprocess.run(
        [sys.executable, str(full_script_path)],
        capture_output=True,
        text=True,
        cwd=str(project_root),  # always run from project root
        env={**__import__('os').environ, 'PYTHONPATH': str(project_root)}
    )

    # Log stdout to Dagster UI
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            context.log.info(line)

    # Log stderr as warnings
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            context.log.warning(line)

    if result.returncode != 0:
        context.log.error(f"STDOUT: {result.stdout}")
        context.log.error(f"STDERR: {result.stderr}")
        raise Exception(f"Script {script_path} failed with return code {result.returncode}")

    return result.returncode

# ── Helper: run a dbt command ─────────────────────────────────────────────────
def run_dbt_command(context: OpExecutionContext, command: str):
    """
    Runs a dbt command inside the medical_warehouse/ subfolder.
    e.g. command = "run" → runs "dbt run" inside medical_warehouse/
    """
    # Get the absolute path to the project root
    project_root = Path(__file__).parent.absolute()

    result = subprocess.run(
        ["dbt", command],
        capture_output=True,
        text=True,
        cwd=str(project_root / "medical_warehouse"),
    )

    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            context.log.info(line)

    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            context.log.warning(line)

    if result.returncode != 0:
        raise Exception(f"dbt {command} failed with return code {result.returncode}")

    return result.returncode


# ── OP 1: Scrape Telegram ─────────────────────────────────────────────────────
@op
def scrape_telegram_data(context: OpExecutionContext):
    """
    Runs the Telegram scraper.
    Extracts messages and images from 3 Ethiopian medical channels.
    Output: JSON files in data/raw/telegram_messages/ and images in data/raw/images/
    """
    context.log.info("Starting Telegram scraping...")
    context.log.info("Channels: @CheMed123, @lobelia4cosmetics, @tikvahpharma")
    run_python_script(context, "src/scraper.py")
    context.log.info("Telegram scraping complete!")


# ── OP 2: Load Raw Data to PostgreSQL ────────────────────────────────────────
@op
def load_raw_to_postgres(context: OpExecutionContext, scrape_result=None):
    """
    Reads all JSON files from the data lake and loads them into
    raw.telegram_messages in PostgreSQL.
    Depends on: scrape_telegram_data
    """
    context.log.info("Loading raw JSON data into PostgreSQL...")
    run_python_script(context, "scripts/load_to_postgres.py")
    context.log.info("Raw data loaded into PostgreSQL!")


# ── OP 3: Run dbt Transformations ────────────────────────────────────────────
@op
def run_dbt_transformations(context: OpExecutionContext, load_result=None):
    """
    Runs dbt run and dbt test to build and validate the star schema.
    Creates: stg_telegram_messages, dim_channels, dim_dates, fct_messages
    Depends on: load_raw_to_postgres
    """
    context.log.info("Running dbt transformations...")
    run_dbt_command(context, "run")
    context.log.info("dbt models built successfully!")

    context.log.info("Running dbt tests...")
    run_dbt_command(context, "test")
    context.log.info("All dbt tests passed!")


# ── OP 4: Run YOLO Enrichment ────────────────────────────────────────────────
@op
def run_yolo_enrichment(context: OpExecutionContext, dbt_result=None):
    """
    Runs YOLOv8 object detection on all downloaded images.
    Then loads detection results into PostgreSQL.
    Depends on: run_dbt_transformations
    """
    context.log.info("Running YOLOv8 object detection on images...")
    run_python_script(context, "src/yolo_detect.py")
    context.log.info("YOLO detection complete!")

    context.log.info("Loading YOLO results into PostgreSQL...")
    run_python_script(context, "scripts/load_yolo_to_postgres.py")
    context.log.info("YOLO results loaded!")


# ── OP 5: Final dbt Run ───────────────────────────────────────────────────────
@op
def run_dbt_final(context: OpExecutionContext, yolo_result=None):
    """
    Runs dbt one more time to build fct_image_detections,
    which depends on the YOLO results loaded in the previous step.
    Depends on: run_yolo_enrichment
    """
    context.log.info("Running final dbt models (including fct_image_detections)...")
    run_dbt_command(context, "run")
    context.log.info("All dbt models including image detections are ready!")


# ── JOB: Wire all ops together ────────────────────────────────────────────────
@job
def medical_telegram_pipeline():
    """
    The full end-to-end pipeline wired together.
    Dagster automatically infers execution order from the
    input/output dependencies between ops.
    """
    scrape = scrape_telegram_data()
    load = load_raw_to_postgres(scrape)
    dbt = run_dbt_transformations(load)
    yolo = run_yolo_enrichment(dbt)
    run_dbt_final(yolo)


# ── SCHEDULE: Run daily at midnight UTC ──────────────────────────────────────
daily_schedule = ScheduleDefinition(
    job=medical_telegram_pipeline,
    cron_schedule="0 0 * * *",  # every day at midnight UTC
    name="daily_medical_pipeline",
)

# ── JOB: Transformation only (skip scraping — data already exists) ────────────
@job
def transform_only_pipeline():
    """
    Runs only the transformation steps — useful when data is already scraped.
    Skips scraping to save time during testing.
    """
    load = load_raw_to_postgres()
    dbt = run_dbt_transformations(load)
    yolo = run_yolo_enrichment(dbt)
    run_dbt_final(yolo)
# ── DEFINITIONS: Register everything with Dagster ────────────────────────────
defs = Definitions(
    jobs=[medical_telegram_pipeline, transform_only_pipeline],
    schedules=[daily_schedule],
)