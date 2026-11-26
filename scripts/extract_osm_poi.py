
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "osm"
LOG_DIR = PROJECT_ROOT / "logs"

RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# Cairo pilot bounding box
# south, west, north, east
CAIRO_BBOX = (29.95, 31.15, 30.15, 31.45)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OVERPASS_QUERY = f"""
[out:json][timeout:180];
(
  node["amenity"="pharmacy"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});
  way["amenity"="pharmacy"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});
  relation["amenity"="pharmacy"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});

  node["shop"="supermarket"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});
  way["shop"="supermarket"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});
  relation["shop"="supermarket"]({CAIRO_BBOX[0]},{CAIRO_BBOX[1]},{CAIRO_BBOX[2]},{CAIRO_BBOX[3]});
);
out center tags;
"""


def setup_logging():
    log_file = LOG_DIR / "osm_extraction.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def extract_osm_data():
    logging.info("Starting Cairo OSM extraction")

    headers = {
        "User-Agent": "DigitalDarkEconomy-CoverageGapIntelligence/1.0"
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": OVERPASS_QUERY},
                headers=headers,
                timeout=240
            )

            response.raise_for_status()
            payload = response.json()

            elements = payload.get("elements", [])

            if not isinstance(elements, list):
                raise ValueError("Invalid Overpass response structure")

            return elements

        except (requests.RequestException, ValueError) as error:
            logging.warning(
                "Attempt %s failed: %s",
                attempt,
                error
            )

            if attempt == 3:
                raise

            time.sleep(attempt * 10)


def normalize_record(element):
    element_type = element.get("type")
    osm_id = element.get("id")
    tags = element.get("tags", {})

    if element_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if osm_id is None or lat is None or lon is None:
        return None

    if tags.get("amenity") == "pharmacy":
        category = "pharmacy"
    elif tags.get("shop") == "supermarket":
        category = "supermarket"
    else:
        return None

    return {
        "source": "OpenStreetMap",
        "source_record_id": f"{element_type}/{osm_id}",
        "osm_type": element_type,
        "osm_id": osm_id,
        "name": tags.get("name"),
        "category_raw": category,
        "latitude": lat,
        "longitude": lon,
        "tags": tags
    }


def save_raw_data(records):
    extracted_at = datetime.now(timezone.utc)

    timestamp = extracted_at.strftime("%Y%m%d_%H%M%S")

    output_file = RAW_DIR / f"cairo_osm_poi_{timestamp}.json"

    output_data = {
        "metadata": {
            "source": "OpenStreetMap",
            "provider": "Overpass API",
            "retrieved_at": extracted_at.isoformat(),
            "area": "Cairo pilot bounding box",
            "bbox": {
                "south": CAIRO_BBOX[0],
                "west": CAIRO_BBOX[1],
                "north": CAIRO_BBOX[2],
                "east": CAIRO_BBOX[3]
            },
            "categories": [
                "pharmacy",
                "supermarket"
            ],
            "record_count": len(records),
            "license": "Open Database License (ODbL)"
        },
        "records": records
    }

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    return output_file


def main():
    setup_logging()

    try:
        elements = extract_osm_data()

        records = []

        for element in elements:
            record = normalize_record(element)

            if record is not None:
                records.append(record)

        output_file = save_raw_data(records)

        pharmacy_count = sum(
            record["category_raw"] == "pharmacy"
            for record in records
        )

        supermarket_count = sum(
            record["category_raw"] == "supermarket"
            for record in records
        )

        logging.info("Extraction completed successfully")
        logging.info("Total records: %s", len(records))
        logging.info("Pharmacies: %s", pharmacy_count)
        logging.info("Supermarkets: %s", supermarket_count)
        logging.info("Output file: %s", output_file)

    except Exception:
        logging.exception("OSM extraction failed")
        raise


if __name__ == "__main__":
    main()
