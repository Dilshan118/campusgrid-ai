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

CREATE TABLE IF NOT EXISTS meter_history (
    record_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    meter_id VARCHAR(50) NOT NULL,
    power_kw DOUBLE PRECISION NOT NULL,
    energy_kwh DOUBLE PRECISION NOT NULL
);

-- pgvector: Policy, Tariff and Comfort Standards Knowledge Base
CREATE TABLE IF NOT EXISTS document_clauses (
    id BIGSERIAL PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    clause_reference VARCHAR(100) NOT NULL,
    effective_date DATE,
    content TEXT NOT NULL,
    embedding vector(384) -- Default for standard sentence-transformers (e.g. all-MiniLM-L6-v2)
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
