-- Initialize PostgreSQL Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Structured Campus Data Tables (Rooms, Courses, Timetables, Users, Equipment, Meter History)
CREATE TABLE IF NOT EXISTS rooms (
    room_id VARCHAR(50) PRIMARY KEY,
    building_name VARCHAR(100) NOT NULL,
    room_type VARCHAR(50) NOT NULL,
    max_capacity INT NOT NULL,
    chiller_zone_id VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS timetables (
    schedule_id SERIAL PRIMARY KEY,
    room_id VARCHAR(50) REFERENCES rooms(room_id),
    course_code VARCHAR(50) NOT NULL,
    day_of_week INT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    expected_students INT NOT NULL
);

-- Column names and types mirror src/domain/entities/telemetry.py :: TelemetryInterval
-- exactly, so MeterHistoryRepository can round-trip the entity without translation.
-- (reading_date, time_slot) is the natural key that get_historical_profile() queries by.
CREATE TABLE IF NOT EXISTS meter_history (
    record_id BIGSERIAL PRIMARY KEY,
    reading_date DATE NOT NULL,
    time_slot VARCHAR(5) NOT NULL,
    base_load_kw DOUBLE PRECISION NOT NULL,
    solar_gen_kw DOUBLE PRECISION NOT NULL,
    outdoor_temp_c DOUBLE PRECISION NOT NULL,
    grid_tariff_lkr_kwh DOUBLE PRECISION NOT NULL,
    zone_occupancy_count INT NOT NULL DEFAULT 0,
    UNIQUE (reading_date, time_slot)
);

CREATE INDEX IF NOT EXISTS idx_meter_history_date ON meter_history (reading_date);

-- pgvector: Policy, Tariff and Comfort Standards Knowledge Base
-- Column set must match src/infrastructure/vector_store/pgvector_store.py, which
-- INSERTs and SELECTs section_title. Omitting it makes every pgvector write fail.
CREATE TABLE IF NOT EXISTS document_clauses (
    id BIGSERIAL PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    clause_reference VARCHAR(100) NOT NULL,
    section_title VARCHAR(255),
    effective_date DATE,
    content TEXT NOT NULL,
    -- 384 dimensions matches EMBEDDING_DIMENSION for all-MiniLM-L6-v2.
    -- Changing the embedding model requires altering this column and re-indexing.
    embedding vector(384)
);

-- Audit and Log Store (Encrypted at rest / Append-only)
-- Column set must match src/infrastructure/database/repositories/audit_log_repository.py.
-- An approval never edits a recommendation row: it appends an 'approval_decision' row whose
-- parent_log_id points at the recommendation. Every row carries a SHA-256 signature chained to
-- the previous row (see src/domain/entities/audit.py :: compute_audit_signature).
CREATE TABLE IF NOT EXISTS audit_log_store (
    log_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    agent_sequence JSONB NOT NULL,
    final_decision JSONB NOT NULL,
    human_approved BOOLEAN DEFAULT FALSE,
    signature VARCHAR(255)
);

-- Idempotent upgrades for databases created from an earlier version of this file.
ALTER TABLE audit_log_store ADD COLUMN IF NOT EXISTS record_type VARCHAR(40) NOT NULL DEFAULT 'dispatch_recommendation';
ALTER TABLE audit_log_store ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) NOT NULL DEFAULT 'not_required';
ALTER TABLE audit_log_store ADD COLUMN IF NOT EXISTS parent_log_id BIGINT REFERENCES audit_log_store(log_id);
ALTER TABLE audit_log_store ADD COLUMN IF NOT EXISTS previous_signature VARCHAR(64);

-- At most one approve/reject decision per recommendation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_one_decision_per_recommendation
    ON audit_log_store (parent_log_id) WHERE record_type = 'approval_decision';

-- Append-only enforcement at the database level, not just in application code.
CREATE OR REPLACE FUNCTION audit_log_store_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log_store is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_store_append_only ON audit_log_store;
CREATE TRIGGER audit_log_store_append_only
    BEFORE UPDATE OR DELETE ON audit_log_store
    FOR EACH ROW EXECUTE FUNCTION audit_log_store_block_mutation();

-- Web Analytics interaction events (query clusters, acceptance funnel, XAI A/B test, citation MRR).
-- Column set must match src/infrastructure/database/repositories/analytics_event_repository.py.
CREATE TABLE IF NOT EXISTS analytics_events (
    event_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(40) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    role VARCHAR(40),
    session_id VARCHAR(100),
    audit_log_id BIGINT,
    ab_variant VARCHAR(40),
    intent VARCHAR(40),
    query_text VARCHAR(500),
    rank INT,
    clause_reference VARCHAR(200),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events (event_type);
