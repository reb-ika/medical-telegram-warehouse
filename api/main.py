"""
api/main.py

FastAPI Analytical API for Ethiopian Medical Telegram Data
----------------------------------------------------------
Exposes 4 analytical endpoints that query our dbt star schema.

Run with:
  uvicorn api.main:app --reload --port 8000

Then visit:
  http://localhost:8000/docs  ← interactive API documentation
"""

from typing import List
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import get_db
from api.schemas import (
    TopProduct,
    ChannelActivity,
    MessageResult,
    VisualContentStat,
)

# ── Create FastAPI app ────────────────────────────────────────────────────────
app = FastAPI(
    title="Ethiopian Medical Telegram Analytics API",
    description="Analytical API exposing insights from Ethiopian medical Telegram channels",
    version="1.0.0",
)


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Health check — confirms the API is running."""
    return {
        "message": "Ethiopian Medical Telegram Analytics API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/api/reports/top-products",
            "/api/channels/{channel_name}/activity",
            "/api/search/messages",
            "/api/reports/visual-content",
        ]
    }


# ── Endpoint 1: Top Products ──────────────────────────────────────────────────
@app.get("/api/reports/top-products", response_model=List[TopProduct])
def get_top_products(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Returns the most frequently mentioned words/terms across all messages.
    Filters out common stop words to return meaningful medical terms.

    Query param: limit (default 10, max 100)
    """
    query = text("""
        WITH words AS (
            SELECT
                lower(regexp_split_to_table(message_text, '\\s+')) AS term
            FROM dev.fct_messages
            WHERE message_text != ''
        ),
        filtered AS (
            SELECT term
            FROM words
            WHERE
                length(term) > 3
                AND term NOT IN (
                    'this', 'that', 'with', 'from', 'have', 'will',
                    'your', 'more', 'also', 'been', 'were', 'they',
                    'their', 'what', 'when', 'which', 'about', 'into',
                    'than', 'then', 'some', 'each', 'much', 'very',
                    'just', 'like', 'only', 'such', 'both', 'over',
                    'after', 'before', 'these', 'those', 'there',
                    'here', 'come', 'made', 'make', 'many', 'most',
                    'other', 'time', 'year', 'good', 'well', 'also',
                    'back', 'even', 'still', 'way', 'because', 'does',
                    'through', 'during', 'where', 'while', 'should'
                )
                AND term ~ '^[a-z]+$'
        )
        SELECT term, COUNT(*) AS mention_count
        FROM filtered
        GROUP BY term
        ORDER BY mention_count DESC
        LIMIT :limit
    """)

    rows = db.execute(query, {"limit": limit}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found")

    return [TopProduct(term=row[0], mention_count=row[1]) for row in rows]


# ── Endpoint 2: Channel Activity ──────────────────────────────────────────────
@app.get("/api/channels/{channel_name}/activity", response_model=ChannelActivity)
def get_channel_activity(
    channel_name: str,
    db: Session = Depends(get_db)
):
    """
    Returns posting activity stats for a specific channel.

    Path param: channel_name (e.g. tikvahpharma, lobelia4cosmetics, CheMed123)
    """
    query = text("""
        SELECT
            c.channel_name,
            c.channel_type,
            c.total_posts,
            c.avg_views,
            to_char(c.first_post_date, 'YYYY-MM-DD') AS first_post_date,
            to_char(c.last_post_date,  'YYYY-MM-DD') AS last_post_date,
            COUNT(f.message_id) FILTER (WHERE f.has_image = true) AS posts_with_images
        FROM dev.dim_channels c
        LEFT JOIN dev.fct_messages f ON c.channel_key = f.channel_key
        WHERE lower(c.channel_name) = lower(:channel_name)
        GROUP BY
            c.channel_name, c.channel_type, c.total_posts,
            c.avg_views, c.first_post_date, c.last_post_date
    """)

    row = db.execute(query, {"channel_name": channel_name}).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found. "
                   f"Try: tikvahpharma, lobelia4cosmetics, CheMed123"
        )

    return ChannelActivity(
        channel_name=row[0],
        channel_type=row[1],
        total_posts=row[2],
        avg_views=float(row[3]),
        first_post_date=row[4],
        last_post_date=row[5],
        posts_with_images=row[6],
    )


# ── Endpoint 3: Message Search ────────────────────────────────────────────────
@app.get("/api/search/messages", response_model=List[MessageResult])
def search_messages(
    query: str = Query(..., min_length=2, description="Search term"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Searches for messages containing a specific keyword.
    Case-insensitive search across all channels.

    Query params:
      query  — search term (e.g. paracetamol, cream, vitamin)
      limit  — max results (default 20)
    """
    sql = text("""
        SELECT
            f.message_id,
            c.channel_name,
            to_char(f.message_date, 'YYYY-MM-DD HH24:MI') AS message_date,
            f.message_text,
            f.views,
            f.forwards,
            f.has_image
        FROM dev.fct_messages f
        JOIN dev.dim_channels c ON f.channel_key = c.channel_key
        WHERE lower(f.message_text) LIKE lower(:search_term)
        ORDER BY f.views DESC
        LIMIT :limit
    """)

    rows = db.execute(sql, {
        "search_term": f"%{query}%",
        "limit": limit
    }).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No messages found containing '{query}'"
        )

    return [
        MessageResult(
            message_id=row[0],
            channel_name=row[1],
            message_date=row[2],
            message_text=row[3],
            views=row[4],
            forwards=row[5],
            has_image=row[6],
        )
        for row in rows
    ]


# ── Endpoint 4: Visual Content Stats ─────────────────────────────────────────
@app.get("/api/reports/visual-content", response_model=List[VisualContentStat])
def get_visual_content_stats(db: Session = Depends(get_db)):
    """
    Returns statistics about image usage across all channels.
    Shows which channels are most visual and what image categories dominate.
    """
    query = text("""
        SELECT
            c.channel_name,
            COUNT(DISTINCT f.message_id)                                AS total_messages,
            COUNT(DISTINCT f.message_id) FILTER (WHERE f.has_image)    AS messages_with_images,
            ROUND(
                100.0 * COUNT(DISTINCT f.message_id) FILTER (WHERE f.has_image)
                / NULLIF(COUNT(DISTINCT f.message_id), 0), 1
            )                                                           AS image_percentage,
            MODE() WITHIN GROUP (ORDER BY i.image_category)            AS top_image_category
        FROM dev.dim_channels c
        LEFT JOIN dev.fct_messages f      ON c.channel_key = f.channel_key
        LEFT JOIN dev.fct_image_detections i ON f.message_id = i.message_id
        GROUP BY c.channel_name
        ORDER BY image_percentage DESC
    """)

    rows = db.execute(query).fetchall()

    return [
        VisualContentStat(
            channel_name=row[0],
            total_messages=row[1],
            messages_with_images=row[2],
            image_percentage=float(row[3] or 0),
            top_image_category=row[4] or "none",
        )
        for row in rows
    ]