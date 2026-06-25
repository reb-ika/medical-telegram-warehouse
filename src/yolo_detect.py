"""
src/yolo_detect.py

YOLOv8 Object Detection for Telegram Medical Images
----------------------------------------------------
Uses the YOLOv8 nano model to detect objects in images
downloaded during Task 1 scraping.

For each image it:
  1. Runs object detection
  2. Records all detected objects with confidence scores
  3. Classifies the image into a category:
       - promotional    → person + product detected
       - product_display → product detected, no person
       - lifestyle       → person detected, no product
       - other           → nothing useful detected

Results are saved to data/yolo_detections.csv
which will be loaded into PostgreSQL in the next step.
"""

import csv
import logging
from pathlib import Path

from ultralytics import YOLO

# ─── Logging setup ───────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/yolo_detect.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ─── YOLO object categories ───────────────────────────────────────────────────
# These are COCO dataset class names that YOLOv8 was trained on.
# We group them into "person" and "product" for our classification scheme.

# Classes that indicate a PERSON is in the image
PERSON_CLASSES = {"person"}

# Classes that suggest a PRODUCT is in the image
# (bottles, boxes, containers are common in medical/cosmetic photos)
PRODUCT_CLASSES = {
    "bottle", "cup", "bowl", "vase", "book",
    "scissors", "toothbrush", "cell phone", "remote",
    "clock", "backpack", "handbag", "suitcase",
    "potted plant", "wine glass", "knife", "spoon"
}

# Minimum confidence score to count a detection (0.0 to 1.0)
# 0.3 means "at least 30% confident" — low enough to catch partial views
CONFIDENCE_THRESHOLD = 0.3


# ─── Image classification logic ───────────────────────────────────────────────
def classify_image(detected_classes: set) -> str:
    """
    Given the set of detected class names in an image,
    returns one of four category labels.

    Logic:
      - person + product  → promotional (someone showing/holding a product)
      - product only      → product_display (product photo, no person)
      - person only       → lifestyle (person, no product)
      - neither           → other
    """
    has_person = bool(detected_classes & PERSON_CLASSES)
    has_product = bool(detected_classes & PRODUCT_CLASSES)

    if has_person and has_product:
        return "promotional"
    elif has_product and not has_person:
        return "product_display"
    elif has_person and not has_product:
        return "lifestyle"
    else:
        return "other"


# ─── Extract message_id and channel from image path ──────────────────────────
def parse_image_path(image_path: Path) -> tuple:
    """
    Image paths look like:
      data/raw/images/tikvahpharma/12345.jpg

    We extract:
      channel_name = "tikvahpharma"
      message_id   = 12345
    """
    channel_name = image_path.parent.name
    message_id = image_path.stem  # filename without extension
    return channel_name, message_id


# ─── Main detection function ──────────────────────────────────────────────────
def run_detection():
    """
    Scans all images in data/raw/images/,
    runs YOLOv8 detection on each one,
    and saves results to data/yolo_detections.csv
    """
    # Load YOLOv8 nano model
    # First run will auto-download yolov8n.pt (~6MB) — small and fast
    logger.info("Loading YOLOv8 nano model...")
    model = YOLO("yolov8n.pt")
    logger.info("Model loaded!")

    # Find all images
    image_folder = Path("data/raw/images")
    image_files = list(image_folder.rglob("*.jpg")) + \
                  list(image_folder.rglob("*.jpeg")) + \
                  list(image_folder.rglob("*.png"))

    logger.info(f"Found {len(image_files)} images to process")

    if not image_files:
        logger.error("No images found! Make sure Task 1 scraper ran successfully.")
        return

    # Output CSV file
    output_path = Path("data/yolo_detections.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results_written = 0
    errors = 0

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            "message_id",
            "channel_name",
            "image_path",
            "detected_class",
            "confidence_score",
            "image_category",
        ])
        writer.writeheader()

        for i, image_path in enumerate(image_files, 1):
            channel_name, message_id = parse_image_path(image_path)
            logger.info(f"[{i}/{len(image_files)}] Processing: {image_path}")

            try:
                # Run YOLO detection
                # verbose=False suppresses per-image console output
                results = model(str(image_path), verbose=False)

                # Collect all detections above confidence threshold
                detections = []
                detected_classes = set()

                for result in results:
                    for box in result.boxes:
                        confidence = float(box.conf[0])

                        if confidence >= CONFIDENCE_THRESHOLD:
                            # Get the class name from the class index
                            class_id = int(box.cls[0])
                            class_name = model.names[class_id]
                            detections.append((class_name, confidence))
                            detected_classes.add(class_name)

                # Classify the image based on what was detected
                image_category = classify_image(detected_classes)

                if detections:
                    # Write one row per detected object
                    for class_name, confidence in detections:
                        writer.writerow({
                            "message_id": message_id,
                            "channel_name": channel_name,
                            "image_path": str(image_path),
                            "detected_class": class_name,
                            "confidence_score": round(confidence, 4),
                            "image_category": image_category,
                        })
                        results_written += 1
                else:
                    # No detections — still record the image with "other" category
                    writer.writerow({
                        "message_id": message_id,
                        "channel_name": channel_name,
                        "image_path": str(image_path),
                        "detected_class": "none",
                        "confidence_score": 0.0,
                        "image_category": "other",
                    })
                    results_written += 1

            except Exception as e:
                logger.error(f"  Failed to process {image_path}: {e}")
                errors += 1
                continue

    logger.info("=" * 50)
    logger.info(f"Detection complete!")
    logger.info(f"Images processed: {len(image_files) - errors}")
    logger.info(f"Rows written to CSV: {results_written}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Results saved to: {output_path}")


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_detection()