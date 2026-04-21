-- Add tsvector column for full-text search on cohesive_profile
ALTER TABLE cohesive_profile ADD COLUMN IF NOT EXISTS search_tsv tsvector;

-- GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_cohesive_profile_search_tsv
    ON cohesive_profile USING GIN (search_tsv);

-- Trigger function to auto-populate search_tsv from embedding_text
CREATE OR REPLACE FUNCTION cohesive_profile_search_tsv_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.search_tsv := to_tsvector('english', COALESCE(NEW.embedding_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists, then create
DROP TRIGGER IF EXISTS trg_cohesive_profile_search_tsv ON cohesive_profile;
CREATE TRIGGER trg_cohesive_profile_search_tsv
    BEFORE INSERT OR UPDATE OF embedding_text ON cohesive_profile
    FOR EACH ROW
    EXECUTE FUNCTION cohesive_profile_search_tsv_trigger();

-- Backfill existing rows
UPDATE cohesive_profile
SET search_tsv = to_tsvector('english', COALESCE(embedding_text, ''))
WHERE search_tsv IS NULL;
