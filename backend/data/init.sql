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
