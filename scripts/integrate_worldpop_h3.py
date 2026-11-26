import hashlib
import getpass
from pathlib import Path

import h3
import numpy as np
import rasterio
import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(r"D:\ZIAD WEB ITI\The_Digital_Dark_Economy")
RASTER = ROOT / "data" / "raw" / "worldpop" / "cairo_worldpop_2025_100m.tif"

print("1. Validating WorldPop raster...")
if not RASTER.exists():
    raise FileNotFoundError(RASTER)

sha256 = hashlib.sha256(RASTER.read_bytes()).hexdigest()

with rasterio.open(RASTER) as ds:
    if ds.crs is None or ds.crs.to_epsg() != 4326:
        raise ValueError(f"Unexpected CRS: {ds.crs}")

    data = ds.read(1, masked=True)
    valid = ~np.ma.getmaskarray(data)
    rows, cols = np.where(valid)
    values = np.asarray(data.data[valid], dtype=np.float64)

    if np.any(values < 0):
        raise ValueError("Negative population values found")

    xs, ys = rasterio.transform.xy(
        ds.transform, rows, cols, offset="center"
    )

    print("Raster:", ds.width, "x", ds.height)
    print("Valid pixels:", len(values))
    print("Raster population sum:", round(float(values.sum()), 2))
    print("SHA256:", sha256)

print("\n2. Aggregating pixels into H3 resolution 8...")
population = {}
pixel_counts = {}

for lat, lon, value in zip(ys, xs, values):
    cell = h3.latlng_to_cell(lat, lon, 8)
    population[cell] = population.get(cell, 0.0) + float(value)
    pixel_counts[cell] = pixel_counts.get(cell, 0) + 1

print("H3 cells containing raster pixels:", len(population))

print("\n3. Connecting to PostgreSQL...")
password = getpass.getpass("PostgreSQL password: ")

with psycopg.connect(
    host="127.0.0.1",
    port=5432,
    dbname="digital_dark_economy",
    user="postgres",
    password=password
) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT run_id, project_id
            FROM model_run
            WHERE run_name = 'OSM H3 Resolution 8 Baseline'
              AND status = 'completed'
            ORDER BY run_id DESC
            LIMIT 1
        """)
        baseline = cur.fetchone()

        if not baseline:
            raise RuntimeError("Completed OSM baseline not found")

        baseline_id, project_id = baseline

        cur.execute("""
            SELECT COUNT(*)
            FROM model_run
            WHERE run_name = 'OSM + WorldPop Cairo 2025'
        """)
        if cur.fetchone()[0]:
            raise RuntimeError(
                "WorldPop run already exists. Stopping to avoid duplicates."
            )

        cur.execute("""
            INSERT INTO source_dataset
                (name, provider, licence, release_id, url, checksum)
            VALUES
                (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name, release_id)
            DO UPDATE SET checksum = EXCLUDED.checksum
            RETURNING source_id
        """, (
            "WorldPop Population Raster",
            "WorldPop",
            "CC BY 4.0",
            "2025-100m-Cairo-Pilot-20261125",
            "https://api.worldpop.org/v3/raster",
            sha256
        ))
        source_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO model_run
                (project_id, run_name, algorithm_version,
                 status, parameters, notes)
            VALUES
                (%s, %s, %s, 'running', %s, %s)
            RETURNING run_id
        """, (
            project_id,
            "OSM + WorldPop Cairo 2025",
            "osm-worldpop-h3-v1",
            Jsonb({
                "h3_resolution": 8,
                "population_year": 2025,
                "raster_resolution": "approximately 100m",
                "source_id": source_id,
                "aggregation": "sum of valid raster pixel values by pixel-center H3 cell"
            }),
            "OSM baseline features copied into a separate run. "
            "WorldPop population values aggregated by H3 cell. "
            "Cells without raster pixels retain NULL population."
        ))
        run_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO cell_features
                (h3_index, run_id, standard_category,
                 poi_count, competitor_count, population_estimate,
                 road_length_km, building_count)
            SELECT
                h3_index, %s, standard_category,
                poi_count, competitor_count, NULL,
                road_length_km, building_count
            FROM cell_features
            WHERE run_id = %s
            ON CONFLICT (h3_index, run_id, standard_category)
            DO NOTHING
        """, (run_id, baseline_id))

        cur.execute("SELECT h3_index::text FROM h3_cell")
        database_cells = {row[0] for row in cur.fetchall()}

        mapped = {
            cell: total
            for cell, total in population.items()
            if cell in database_cells
        }

        updates = [
            (round(total, 2), cell, run_id)
            for cell, total in mapped.items()
        ]

        cur.executemany("""
            UPDATE cell_features
            SET population_estimate = %s,
                calculated_at = NOW()
            WHERE h3_index = %s::h3index
              AND run_id = %s
        """, updates)

        cur.execute("""
            UPDATE model_run
            SET status = 'completed',
                completed_at = NOW()
            WHERE run_id = %s
        """, (run_id,))

        cur.execute("""
            SELECT
                COUNT(DISTINCT h3_index),
                COUNT(*),
                COUNT(population_estimate),
                ROUND(SUM(population_estimate), 2)
            FROM cell_features
            WHERE run_id = %s
        """, (run_id,))
        stats = cur.fetchone()

        conn.commit()

print("\n========== WORLDPOP INTEGRATION SUCCESS ==========")
print("Source ID:", source_id)
print("Baseline run:", baseline_id)
print("New run:", run_id)
print("H3 cells in database:", len(database_cells))
print("Cells receiving population:", len(mapped))
print("Cells without raster pixels:", len(database_cells) - len(mapped))
print("Raster population mapped to project:", round(sum(mapped.values()), 2))
print("Feature cells:", stats[0])
print("Feature rows:", stats[1])
print("Rows with population:", stats[2])
print("Population sum across category rows:", stats[3])
print("==================================================")

