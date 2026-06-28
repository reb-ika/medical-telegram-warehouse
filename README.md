# Medical Telegram Data Warehouse

A polished ELT analytics pipeline for Ethiopian medical Telegram content.
This repository ingests Telegram messages, stores raw data in PostgreSQL,
transforms it with dbt into a dimensional star schema, enriches image content
with YOLOv8 object detection, and exposes analytics through a FastAPI service.

**Built for:** 10 Academy Kifiya AI Training Programme — Week 8

**Author:** Rebika Woldeyesus


---

## Overview

This project provides a reproducible analytics workflow for Telegram channel
data:

- **Telegram scraping** for message and media ingestion
- **PostgreSQL raw landing zone** for data persistence
- **dbt transformations** into a clean star schema
- **YOLOv8 enrichment** for image detection metadata
- **FastAPI analytics API** for exploration and reporting

---

## Architecture

```text
Telegram channels
      ↓
Telethon scraper (src/scraper.py)
      ↓
Raw JSON data lake (data/raw/telegram_messages/YYYY-MM-DD/)
      ↓
PostgreSQL raw schema (scripts/load_to_postgres.py)
      ↓
dbt transforms (medical_warehouse/)
      ↓
Star schema in dev schema
      ↓
FastAPI analytics API (api/main.py)
```

---

## Channels Scraped

| Channel | Type | Messages |
|---------|------|----------|
| @CheMed123 | Medical | ~76 |
| @lobelia4cosmetics | Cosmetics | ~200 |
| @tikvahpharma | Pharmaceutical | ~200 |

---

## Prerequisites

- Python 3.10+
- PostgreSQL 18 (running on port 5433)
- Git

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/medical-telegram-warehouse.git
cd medical-telegram-warehouse
```

### 2. Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root (never commit this):

```env
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash

POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=medical_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

Get Telegram API credentials at: https://my.telegram.org

### 5. Configure dbt

Copy `profiles.yml` from the project root to your dbt directory:

```powershell
# Windows
Copy-Item profiles.yml "$env:USERPROFILE\.dbt\profiles.yml"
```

Then edit `C:\Users\<you>\.dbt\profiles.yml` and replace `your_postgres_password_here` with your actual password.

### 6. Create the PostgreSQL Database

```powershell
psql -U postgres -p 5433 -c "CREATE DATABASE medical_warehouse;"
```

---

## Running the Pipeline

Use the commands below to execute the full workflow.

### Step 1 — Scrape Telegram data

```powershell
python src/scraper.py
```

This step collects Telegram messages and saves raw JSON to `data/raw/telegram_messages/`.

### Step 2 — Load raw data into PostgreSQL

```powershell
python scripts/load_to_postgres.py
```

This loads messages into the raw PostgreSQL schema for downstream transformation.

### Step 3 — Run dbt models

```powershell
cd medical_warehouse
dbt run
dbt test
```

This builds the star schema and validates data quality.

### Step 4 — Enrich images with YOLOv8

```powershell
cd ..
python src/yolo_detect.py
python scripts/load_yolo_to_postgres.py
cd medical_warehouse
dbt run
```

This detects image objects and loads detection results into the analytics schema.

### Step 5 — Start the FastAPI API

```powershell
cd ..
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` to explore the API.

---

## dbt Star Schema

```text
dim_channels
       (channel_key PK)
            |
            dim_dates ── fct_messages ── fct_image_detections

(date_key PK)  (central fact)    (YOLO results)
```

### Models

| Model | Type | Description |
|-------|------|-------------|
| `stg_telegram_messages` | View | Cleans and standardizes raw Telegram messages |
| `dim_channels` | Table | Channel metadata and summary stats |
| `dim_dates` | Table | Date dimension for time-based analysis |
| `fct_messages` | Table | Message-level analytics fact table |
| `fct_image_detections` | Table | YOLO image detection results |

### Data quality tests

- `unique` and `not_null` for primary keys
- `relationships` for foreign key integrity
- `assert_no_future_messages` custom test

Run `dbt test` from `medical_warehouse/` to validate the models.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check and endpoint listing |
| `GET` | `/api/reports/top-products` | Top mentioned terms across all messages |
| `GET` | `/api/channels/{channel_name}/activity` | Channel-level activity and image stats |
| `GET` | `/api/search/messages` | Search messages by keyword |
| `GET` | `/api/reports/visual-content` | Visual content analytics by channel |

Visit `http://localhost:8000/docs` for full API documentation.

---

## Project Structure

```text
medical-telegram-warehouse/

├── .env                        
├── .gitignore

├── profiles.yml                  

├── requirements.txt

├── README.md

├── data/

│   ├── raw/

│   │   ├── telegram_messages/    

│   │   └── images/              

│   └── yolo_detections.csv      

├── medical_warehouse/           

│   ├── dbt_project.yml

│   ├── models/

│   │   ├── staging/

│   │   │   └── stg_telegram_messages.sql

│   │   └── marts/

│   │       ├── dim_channels.sql

│   │       ├── dim_dates.sql

│   │       ├── fct_messages.sql

│   │       ├── fct_image_detections.sql

│   │       └── schema.yml

│   └── tests/

│       └── assert_no_future_messages.sql

├── src/

│   ├── scraper.py                
│   └── yolo_detect.py            

├── scripts/

│   ├── load_to_postgres.py       

│   └── load_yolo_to_postgres.py  

├── api/

│   ├── main.py                   

│   ├── database.py              

│   └── schemas.py                

└── logs/                        
---

