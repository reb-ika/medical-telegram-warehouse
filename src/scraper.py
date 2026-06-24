"""
src/scraper.py

Telegram Scraper for Ethiopian Medical Channels
------------------------------------------------
Uses Telethon (async Telegram client library) to:
- Connect to Telegram using your API credentials
- Scrape messages from public medical channels
- Download images when present
- Save everything as structured JSON files in a data lake format

Data Lake structure:
  data/raw/telegram_messages/YYYY-MM-DD/channel_name.json
  data/raw/images/channel_name/message_id.jpg
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import time

# ─── Load environment variables from .env ───────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

# ─── Channels to scrape ─────────────────────────────────────────────────────
CHANNELS = [
    "@CheMed123",
    "@lobelia4cosmetics",
    "@tikvahpharma",
]

# How many messages to scrape per channel (start small to test)
MESSAGE_LIMIT = 200

# ─── Set up logging ──────────────────────────────────────────────────────────
# This creates a logs/ folder and writes both to file and terminal
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(),  # also print to terminal
    ],
)
logger = logging.getLogger(__name__)


# ─── Helper: save messages as JSON ───────────────────────────────────────────
def save_messages_to_json(messages: list, channel_name: str, date_str: str):
    """
    Saves a list of message dicts to:
      data/raw/telegram_messages/YYYY-MM-DD/channel_name.json

    The date-partitioned structure makes it easy to reprocess
    specific days without touching everything else.
    """
    # Remove the @ from channel name for file/folder naming
    clean_channel = channel_name.lstrip("@")

    # Create the date-partitioned folder
    folder = Path(f"data/raw/telegram_messages/{date_str}")
    folder.mkdir(parents=True, exist_ok=True)

    filepath = folder / f"{clean_channel}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"  Saved {len(messages)} messages → {filepath}")


# ─── Main scraping function ───────────────────────────────────────────────────
async def scrape_channel(client: TelegramClient, channel: str):
    """
    Scrapes one Telegram channel and saves:
    - Messages as JSON
    - Images to data/raw/images/channel_name/

    For each message we collect:
      message_id, channel_name, message_date, message_text,
      has_media, image_path, views, forwards
    """
    clean_channel = channel.lstrip("@")
    logger.info(f"Starting scrape: {channel}")

    # Folder for this channel's images
    image_folder = Path(f"data/raw/images/{clean_channel}")
    image_folder.mkdir(parents=True, exist_ok=True)

    messages_by_date = {}  # group messages by date for partitioned storage

    try:
        # iter_messages loops through messages newest-first
        async for message in client.iter_messages(channel, limit=MESSAGE_LIMIT):

            # ── Extract basic fields ──────────────────────────────────────
            msg_date = message.date  # this is a datetime object (UTC)
            date_str = msg_date.strftime("%Y-%m-%d")  # e.g. "2026-06-24"

            has_media = message.photo is not None  # True if message has a photo
            image_path = None

            # ── Download image if present ─────────────────────────────────
            if has_media:
                img_filename = f"{message.id}.jpg"
                img_path = image_folder / img_filename

                # Only download if we haven't already (avoid re-downloading on re-runs)
                if not img_path.exists():
                    try:
                        await client.download_media(message.photo, file=str(img_path))
                        logger.info(f"    Downloaded image: {img_path}")
                    except Exception as e:
                        logger.warning(f"    Failed to download image for msg {message.id}: {e}")
                        has_media = False

                if img_path.exists():
                    image_path = str(img_path)

            # ── Build the message record ──────────────────────────────────
            record = {
                "message_id": message.id,
                "channel_name": clean_channel,
                "message_date": msg_date.isoformat(),   # store as ISO string
                "message_text": message.text or "",      # some messages are image-only
                "has_media": has_media,
                "image_path": image_path,
                "views": message.views or 0,
                "forwards": message.forwards or 0,
            }

            # ── Group by date for partitioned JSON files ──────────────────
            if date_str not in messages_by_date:
                messages_by_date[date_str] = []
            messages_by_date[date_str].append(record)

        # ── Save each date's messages to its own JSON file ────────────────
        for date_str, msgs in messages_by_date.items():
            save_messages_to_json(msgs, channel, date_str)

        total = sum(len(v) for v in messages_by_date.values())
        logger.info(f"Finished {channel}: {total} messages across {len(messages_by_date)} dates")

    except FloodWaitError as e:
        # Telegram rate-limits you if you scrape too fast — we wait and retry
        logger.warning(f"Rate limited on {channel}. Waiting {e.seconds} seconds...")
        time.sleep(e.seconds + 5)

    except Exception as e:
        logger.error(f"Error scraping {channel}: {e}")


# ─── Entry point ──────────────────────────────────────────────────────────────
async def main():
    logger.info("=" * 60)
    logger.info("Medical Telegram Scraper Started")
    logger.info(f"Channels: {CHANNELS}")
    logger.info(f"Message limit per channel: {MESSAGE_LIMIT}")
    logger.info("=" * 60)

    # TelegramClient needs a session name — it creates a .session file locally
    # so you don't have to log in every time
    async with TelegramClient("telegram_session", API_ID, API_HASH) as client:
        for channel in CHANNELS:
            await scrape_channel(client, channel)
            # Small pause between channels to be polite to Telegram's servers
            await asyncio.sleep(3)

    logger.info("All channels scraped successfully!")


if __name__ == "__main__":
    asyncio.run(main())