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

-- Seed inventory, identical to the in-memory repositories. Without rooms, Postgres mode knows no
-- room capacity, so a campus-wide headcount could be simulated inside a single lecture hall.
-- Safe to re-run: existing rows are left alone.
-- room_type must match a venue type in src/agents/digital_twin/room_presets.py.
INSERT INTO rooms (room_id, building_name, room_type, max_capacity, chiller_zone_id) VALUES
    ('LH-1', 'Main Academic Complex', 'Lecture Hall', 250, 'ZONE-A1'),
    ('LH-2', 'Main Academic Complex', 'Lecture Hall', 150, 'ZONE-A1'),
    ('LH-3', 'Main Academic Complex', 'Lecture Hall', 100, 'ZONE-A2'),
    ('LH-4', 'New Academic Building', 'Lecture Hall', 200, 'ZONE-D1'),
    ('LH-5', 'New Academic Building', 'Lecture Hall', 60, 'ZONE-D1'),
    ('LAB-1', 'Computing Building', 'Computer Lab', 40, 'ZONE-C1'),
    ('LAB-2', 'Computing Building', 'Computer Lab', 60, 'ZONE-C1'),
    ('LAB-3', 'Computing Building', 'Computer Lab', 80, 'ZONE-C2'),
    ('SLAB-1', 'Science Block', 'Science Lab', 25, 'ZONE-S1'),
    ('SLAB-2', 'Science Block', 'Science Lab', 35, 'ZONE-S1'),
    ('SLAB-3', 'Engineering Building', 'Science Lab', 30, 'ZONE-E1'),
    ('AUD-1', 'Auditorium Wing', 'Auditorium', 600, 'ZONE-B1'),
    ('AUD-2', 'Business School', 'Auditorium', 300, 'ZONE-B2'),
    ('STDY-1', 'Library', 'Study Area', 150, 'ZONE-L1'),
    ('STDY-2', 'Library', 'Study Area', 60, 'ZONE-L1'),
    ('STDY-3', 'Student Centre', 'Study Area', 80, 'ZONE-T1'),
    ('DRW-1', 'Architecture Building', 'Drawing Room', 40, 'ZONE-R1'),
    ('DRW-2', 'Engineering Building', 'Drawing Room', 60, 'ZONE-E2'),
    ('SEM-1', 'Main Academic Complex', 'Seminar Room', 30, 'ZONE-A2'),
    ('SEM-2', 'Business School', 'Seminar Room', 20, 'ZONE-B2')
ON CONFLICT (room_id) DO NOTHING;

-- day_of_week: 1 = Monday ... 7 = Sunday (ISO weekday, as Agent 1 derives it from the date).
INSERT INTO timetables (room_id, course_code, day_of_week, start_time, end_time, expected_students)
SELECT v.room_id, v.course_code, v.day_of_week, v.start_time::time, v.end_time::time, v.expected_students
FROM (VALUES
    ('LH-1', 'IT3041', 1, '08:30', '11:30', 220),
    ('LH-1', 'IT3020', 1, '13:00', '16:00', 240),
    ('AUD-1', 'EN1010', 1, '09:00', '12:00', 550)
) AS v(room_id, course_code, day_of_week, start_time, end_time, expected_students)
WHERE NOT EXISTS (
    SELECT 1 FROM timetables t
    WHERE t.room_id = v.room_id AND t.course_code = v.course_code AND t.day_of_week = v.day_of_week
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
    provenance_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
    source_uri TEXT,
    content_sha256 VARCHAR(64),
    source_sha256 VARCHAR(64),
    -- 768 dimensions matches Google gemini-embedding-001 / text-embedding-004.
    -- If using sentence-transformers/all-MiniLM-L6-v2, change this to vector(384).
    embedding vector(768)
);

-- Existing rows default to unverified; never promote legacy rows based on their titles.
ALTER TABLE document_clauses ADD COLUMN IF NOT EXISTS provenance_status VARCHAR(32) NOT NULL DEFAULT 'unverified';
ALTER TABLE document_clauses ADD COLUMN IF NOT EXISTS source_uri TEXT;
ALTER TABLE document_clauses ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);
ALTER TABLE document_clauses ADD COLUMN IF NOT EXISTS source_sha256 VARCHAR(64);

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

-- At most one Works Division execution report per approved plan.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_one_execution_per_recommendation
    ON audit_log_store (parent_log_id) WHERE record_type = 'execution_report';

-- At most one review of each quarantined regulation submission.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_one_review_per_submission
    ON audit_log_store (parent_log_id) WHERE record_type = 'knowledge_review';

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
