-- Helper function to insert zip boundaries from WKT string
CREATE OR REPLACE FUNCTION insert_zip_boundary(
  p_zipcode TEXT,
  p_state TEXT,
  p_geometry_wkt TEXT
)
RETURNS VOID AS $$
BEGIN
  INSERT INTO zip_boundaries (zipcode, state, geometry)
  VALUES (p_zipcode, p_state, ST_GeomFromText(p_geometry_wkt, 4326))
  ON CONFLICT (zipcode) DO UPDATE
  SET geometry = ST_GeomFromText(p_geometry_wkt, 4326),
      state = p_state;
END;
$$ LANGUAGE plpgsql;
