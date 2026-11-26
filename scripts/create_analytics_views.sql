CREATE OR REPLACE VIEW v_latest_cell_features AS
SELECT
    f.run_id,
    mr.run_name,
    f.h3_index,
    c.resolution,
    f.standard_category,
    f.poi_count,
    f.competitor_count,
    f.population_estimate,
    f.road_length_km,
    f.building_count,
    c.area_sq_km,
    c.geom,
    c.centroid,
    f.calculated_at
FROM cell_features f
JOIN h3_cell c ON c.h3_index = f.h3_index
JOIN model_run mr ON mr.run_id = f.run_id
WHERE f.run_id = (
    SELECT run_id
    FROM model_run
    WHERE status = 'completed'
    ORDER BY run_id DESC
    LIMIT 1
);

CREATE OR REPLACE VIEW v_latest_cell_summary AS
SELECT
    f.run_id,
    f.h3_index,
    c.resolution,
    MAX(CASE WHEN f.standard_category = 'pharmacy'
        THEN f.poi_count END) AS pharmacy_count,
    MAX(CASE WHEN f.standard_category = 'supermarket'
        THEN f.poi_count END) AS supermarket_count,
    MAX(f.population_estimate) AS population_estimate,
    MAX(f.road_length_km) AS road_length_km,
    MAX(f.building_count) AS building_count,
    c.area_sq_km,
    c.geom,
    c.centroid
FROM cell_features f
JOIN h3_cell c ON c.h3_index = f.h3_index
WHERE f.run_id = (
    SELECT run_id
    FROM model_run
    WHERE status = 'completed'
    ORDER BY run_id DESC
    LIMIT 1
)
GROUP BY f.run_id, f.h3_index, c.resolution,
         c.area_sq_km, c.geom, c.centroid;

CREATE OR REPLACE VIEW v_poi_category_summary AS
SELECT
    standard_category,
    COUNT(*) AS total_entities,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_entities,
    COUNT(*) FILTER (WHERE name IS NOT NULL AND name <> '') AS named_entities
FROM poi_entity
GROUP BY standard_category;

CREATE OR REPLACE VIEW v_latest_data_quality AS
SELECT
    run_id,
    COUNT(*) AS total_feature_rows,
    COUNT(DISTINCT h3_index) AS total_h3_cells,
    COUNT(*) FILTER (WHERE population_estimate IS NOT NULL) AS populated_rows,
    COUNT(*) FILTER (WHERE population_estimate IS NULL) AS missing_population_rows,
    COUNT(*) FILTER (WHERE road_length_km IS NULL) AS missing_road_rows,
    COUNT(*) FILTER (WHERE building_count IS NULL) AS missing_building_rows,
    COUNT(*) FILTER (WHERE road_length_km < 0) AS negative_road_rows,
    COUNT(*) FILTER (WHERE building_count < 0) AS negative_building_rows
FROM cell_features
WHERE run_id = (
    SELECT run_id
    FROM model_run
    WHERE status = 'completed'
    ORDER BY run_id DESC
    LIMIT 1
)
GROUP BY run_id;
