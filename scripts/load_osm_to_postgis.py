
import json
import hashlib
from pathlib import Path
from getpass import getpass
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "osm"
    / "cairo_osm_poi_20261125_022046.json"
)

DATABASE = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "digital_dark_economy",
    "user": "postgres",
}


def main():
    print("Reading OSM JSON file...")

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    metadata = data["metadata"]
    records = data["records"]

    checksum = hashlib.sha256(
        INPUT_FILE.read_bytes()
    ).hexdigest()

    retrieved_at = datetime.fromisoformat(
        metadata["retrieved_at"]
    )

    print(f"Records found: {len(records)}")
    print("Connecting to PostgreSQL...")

    DATABASE["password"] = getpass(
        "Enter PostgreSQL password: "
    )

    with psycopg.connect(**DATABASE) as conn:
        with conn.cursor() as cur:

            # Register the source dataset
            cur.execute(
                """
                INSERT INTO source_dataset
                (name, provider, licence, release_id,
                 retrieved_at, url, checksum)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name, release_id) DO NOTHING
                """,
                (
                    "OpenStreetMap POI",
                    "Overpass API",
                    "ODbL",
                    metadata["retrieved_at"],
                    retrieved_at,
                    "https://overpass-api.de/api/interpreter",
                    checksum,
                ),
            )

            cur.execute(
                """
                SELECT source_id
                FROM source_dataset
                WHERE name = %s AND release_id = %s
                """,
                (
                    "OpenStreetMap POI",
                    metadata["retrieved_at"],
                ),
            )

            source_id = cur.fetchone()[0]

            # Load raw records without duplicating existing IDs
            rows = [
                (
                    source_id,
                    record["source_record_id"],
                    record["name"],
                    record["category_raw"],
                    record["longitude"],
                    record["latitude"],
                    Jsonb(record["tags"]),
                )
                for record in records
            ]

            cur.executemany(
                """
                INSERT INTO raw_poi
                (source_id, source_record_id, name,
                 category_raw, geom, tags)
                VALUES (
                    %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s
                )
                ON CONFLICT (source_id, source_record_id)
                DO NOTHING
                """,
                rows,
            )

            cur.execute(
                """
                SELECT COUNT(*)
                FROM raw_poi
                WHERE source_id = %s
                """,
                (source_id,),
            )

            stored_count = cur.fetchone()[0]

    print("\nLoading completed successfully.")
    print(f"Source ID: {source_id}")
    print(f"Records in source file: {len(records)}")
    print(f"Records stored for this source: {stored_count}")
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
