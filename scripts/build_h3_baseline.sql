
BEGIN;

SET LOCAL h3.strict = true;

DO $$
DECLARE
    v_project_id BIGINT;
    v_run_id BIGINT;
    v_study_area GEOMETRY;
    v_cell_count INTEGER;
    v_feature_count INTEGER;
BEGIN

    -- 1. Create or reuse the Cairo pilot project
    SELECT project_id, study_area
    INTO v_project_id, v_study_area
    FROM client_project
    WHERE project_name = 'The Digital Dark Economy - Cairo Pilot'
    ORDER BY project_id
    LIMIT 1;

    IF v_project_id IS NULL THEN
        INSERT INTO client_project (
            project_name,
            client_name,
            description,
            study_area,
            target_categories,
            status
        )
        VALUES (
            'The Digital Dark Economy - Cairo Pilot',
            'Internal Project',
            'Cairo pilot bounding box for Coverage Gap Intelligence. This is not an official administrative boundary.',
            ST_Multi(
                ST_MakeEnvelope(31.15, 29.95, 31.45, 30.15, 4326)
            ),
            '["pharmacy", "supermarket"]'::JSONB,
            'active'
        )
        RETURNING project_id, study_area
        INTO v_project_id, v_study_area;
    END IF;

    -- 2. Create or reuse the H3 baseline model run
    SELECT run_id
    INTO v_run_id
    FROM model_run
    WHERE project_id = v_project_id
      AND run_name = 'OSM H3 Resolution 8 Baseline'
    ORDER BY run_id
    LIMIT 1;

    IF v_run_id IS NULL THEN
        INSERT INTO model_run (
            project_id,
            run_name,
            algorithm_version,
            status,
            parameters,
            notes
        )
        VALUES (
            v_project_id,
            'OSM H3 Resolution 8 Baseline',
            'osm-h3-baseline-v1',
            'completed',
            '{"h3_resolution": 8, "categories": ["pharmacy", "supermarket"]}'::JSONB,
            'Baseline POI aggregation only. Population, roads and buildings have not yet been integrated.'
        )
        RETURNING run_id INTO v_run_id;
    END IF;

    -- 3. Generate H3 cells covering the pilot area.
    -- Include cells containing POIs even if their centers are outside the bbox.
    INSERT INTO h3_cell (
        h3_index,
        resolution,
        geom,
        centroid,
        area_sq_km
    )
    SELECT
        cells.h3_index,
        8,
        ST_SetSRID(
            h3_cell_to_boundary_geometry(cells.h3_index),
            4326
        ),
        ST_SetSRID(
            h3_cell_to_geometry(cells.h3_index),
            4326
        ),
        h3_cell_area(cells.h3_index, 'km^2')
    FROM (
        SELECT h3_polygon_to_cells_experimental(
            v_study_area,
            8,
            'center'
        ) AS h3_index

        UNION

        SELECT h3_latlng_to_cell(p.geom, 8)
        FROM poi_entity p
        WHERE p.is_active = TRUE
          AND p.standard_category IN ('pharmacy', 'supermarket')
    ) AS cells
    ON CONFLICT (h3_index) DO NOTHING;

    GET DIAGNOSTICS v_cell_count = ROW_COUNT;

    -- 4. Calculate POI counts for both categories in every H3 cell.
    INSERT INTO cell_features (
        h3_index,
        run_id,
        standard_category,
        poi_count,
        competitor_count,
        calculated_at
    )
    SELECT
        c.h3_index,
        v_run_id,
        categories.category,
        COUNT(p.poi_id)::INTEGER,
        COUNT(p.poi_id)::INTEGER,
        NOW()
    FROM h3_cell c
    CROSS JOIN (
        VALUES ('pharmacy'), ('supermarket')
    ) AS categories(category)
    LEFT JOIN poi_entity p
        ON h3_latlng_to_cell(p.geom, 8) = c.h3_index
       AND p.standard_category = categories.category
       AND p.is_active = TRUE
    WHERE c.resolution = 8
    GROUP BY c.h3_index, categories.category
    ON CONFLICT (h3_index, run_id, standard_category)
    DO UPDATE SET
        poi_count = EXCLUDED.poi_count,
        competitor_count = EXCLUDED.competitor_count,
        calculated_at = NOW();

    GET DIAGNOSTICS v_feature_count = ROW_COUNT;

    -- 5. Report execution results
    RAISE NOTICE 'Project ID: %', v_project_id;
    RAISE NOTICE 'Model Run ID: %', v_run_id;
    RAISE NOTICE 'New H3 cells inserted: %', v_cell_count;
    RAISE NOTICE 'Cell feature rows inserted or updated: %', v_feature_count;

END $$;

COMMIT;

