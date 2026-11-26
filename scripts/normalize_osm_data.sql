
BEGIN;

-- 1. Register standard category mappings
INSERT INTO category_map
    (source_name, source_category, standard_category)
VALUES
    ('OpenStreetMap', 'pharmacy', 'pharmacy'),
    ('OpenStreetMap', 'supermarket', 'supermarket')
ON CONFLICT (source_name, source_category) DO NOTHING;


-- 2. Create normalized entities and source links
DO $$
DECLARE
    rec RECORD;
    new_poi_id BIGINT;
BEGIN
    FOR rec IN
        SELECT
            r.raw_poi_id,
            r.name,
            r.geom,
            r.tags,
            cm.standard_category
        FROM raw_poi r
        JOIN source_dataset sd
            ON sd.source_id = r.source_id
        JOIN category_map cm
            ON cm.source_name = 'OpenStreetMap'
           AND cm.source_category = r.category_raw
        WHERE r.source_id = 1
          AND NOT EXISTS (
              SELECT 1
              FROM poi_source_link l
              WHERE l.raw_poi_id = r.raw_poi_id
          )
    LOOP
        INSERT INTO poi_entity
            (name, standard_category, geom, address)
        VALUES (
            rec.name,
            rec.standard_category,
            rec.geom,
            NULLIF(
                CONCAT_WS(
                    ', ',
                    rec.tags ->> 'addr:housenumber',
                    rec.tags ->> 'addr:street'
                ),
                ''
            )
        )
        RETURNING poi_id INTO new_poi_id;

        INSERT INTO poi_source_link
            (poi_id, raw_poi_id, match_method, confidence)
        VALUES (
            new_poi_id,
            rec.raw_poi_id,
            'source_record_exact',
            1.0
        );
    END LOOP;
END $$;

COMMIT;
