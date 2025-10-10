-- Enable PostGIS extension for geospatial operations
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create zip_boundaries table to store zip code polygons
CREATE TABLE IF NOT EXISTS zip_boundaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zipcode TEXT NOT NULL UNIQUE,
    state TEXT,
    geometry GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create spatial index for fast point-in-polygon queries
CREATE INDEX idx_zip_boundaries_geometry ON zip_boundaries USING GIST (geometry);

-- Create function to get zip code for a point
CREATE OR REPLACE FUNCTION get_zipcode_for_point(lon DOUBLE PRECISION, lat DOUBLE PRECISION)
RETURNS TEXT AS $$
  SELECT zipcode
  FROM zip_boundaries
  WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
  LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- Add comments
COMMENT ON TABLE zip_boundaries IS 'Zip code boundary polygons for geospatial filtering';
COMMENT ON FUNCTION get_zipcode_for_point IS 'Returns zip code for a given lon/lat coordinate using PostGIS';
