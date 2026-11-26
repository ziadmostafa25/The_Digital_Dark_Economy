# The Digital Dark Economy
## Coverage Gap Intelligence — Cairo Pilot

A geospatial data engineering project that prepares location-based datasets for analyzing potential service coverage gaps in Cairo.

### Current project status

The Cairo pilot data engineering pipeline has successfully integrated:

| Dataset | Records / Coverage |
|---|---:|
| OSM pharmacies | 183 |
| OSM supermarkets | 534 |
| OSM roads | 123,094 |
| OSM buildings | 66,193 |
| WorldPop population raster | 2025, 100m |
| H3 resolution 8 grid | 743 cells |
| Latest analytical feature rows | 1,486 |

Latest completed model run:
`OSM + WorldPop + Roads & Buildings Cairo` (run ID 4).

### Technology stack

- Python
- PostgreSQL 18
- PostGIS 3.7
- H3 4.5
- Psycopg 3
- Shapely
- Rasterio
- Requests
- SQL

### Data sources and licenses

- OpenStreetMap — ODbL.
- WorldPop — CC BY 4.0.

OSM-derived outputs must retain appropriate attribution and comply with ODbL.
WorldPop values are modeled population estimates, not verified current population counts.

### Database

Database name: `digital_dark_economy`

Core tables include:
- `source_dataset`
- `raw_poi`
- `raw_spatial_feature`
- `poi_entity`
- `poi_source_link`
- `category_map`
- `h3_cell`
- `client_project`
- `model_run`
- `cell_features`
- `completeness_estimate`
- `gap_score`
- `field_observation`

Required PostgreSQL extensions:
- `postgis`
- `postgis_raster`
- `h3`
- `h3_postgis`

### Analytical views

- `v_latest_cell_features`: latest category-level cell features.
- `v_latest_cell_summary`: one summarized row per H3 cell.
- `v_poi_category_summary`: POI category totals.
- `v_latest_data_quality`: latest run data-quality indicators.

### Main scripts

| File | Purpose |
|---|---|
| `scripts/extract_osm_poi.py` | Extract Cairo pharmacies and supermarkets |
| `scripts/load_osm_to_postgis.py` | Load raw POIs into PostgreSQL |
| `scripts/normalize_osm_data.sql` | Normalize categories and link source records |
| `build_h3_baseline.sql` | Build H3 baseline |
| `scripts/integrate_worldpop_h3.py` | Integrate WorldPop population |
| `scripts/integrate_osm_roads_buildings.py` | Extract and integrate roads and buildings |
| `scripts/create_analytics_views.sql` | Create analytical views |
| `create_remaining_schema.sql` | Create the remaining database schema |

### Pilot area

The pilot uses the following rectangular bounding box:
- South: 29.95
- West: 31.15
- North: 30.15
- East: 31.45

This is a project-defined pilot boundary, not an official Cairo administrative boundary.

### Data quality and limitations

The latest completed run contains:
- 743 H3 cells.
- 1,486 category-level feature rows.
- 1,480 rows with population estimates.
- No missing road-length or building-count values.
- No negative road-length or building-count values.

Three H3 cells have no available population raster values. Population is duplicated across the two category rows for each cell; aggregate population only once per H3 cell.

OSM coverage completeness has not yet been independently measured. Missing mapped businesses must not automatically be interpreted as genuine service gaps or low demand.

The Opportunity Score and completeness assessment require further analytical design and validation. This repository does not claim that a validated market-gap score has already been produced.

### Running the project

1. Install PostgreSQL 18 and the required PostGIS and H3 extensions.
2. Create the `digital_dark_economy` database.
3. Apply the schema SQL files in the documented project workflow.
4. Install the Python dependencies required by the scripts.
5. Run extraction, loading, normalization, and integration scripts in sequence.
6. Create the analytical views using `scripts/create_analytics_views.sql`.

Use your own PostgreSQL credentials. Never commit passwords, API keys, or `.env` files.

### Repository contents

Raw datasets, local database backups, temporary PostGIS installation files, and machine-specific files are intentionally excluded from Git. They should be managed separately with their source attribution and licenses.

