
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── enums ───────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin','manager','operator');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE tour_status AS ENUM (
        'draft','confirmed','queued','processing',
        'submitted','completed','failed','cancelled'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE dispatch_job_status AS ENUM ('draft','queued','sending','sent','failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── 1. users ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'operator',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);


-- ── 2. tours ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tours (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Google Sheets
    spreadsheet_id      VARCHAR(255),
    spreadsheet_name    VARCHAR(255),
    sheet_name          VARCHAR(255),

    -- Даты
    date_start          VARCHAR(20) NOT NULL,      -- "17.02.2026"
    date_end            VARCHAR(20) NOT NULL,      -- "24.02.2026"
    days                INTEGER NOT NULL,

    -- Маршрут
    route               VARCHAR(50),               -- "ALA-JED"
    departure_city      VARCHAR(100),
    airlines            VARCHAR(50),               -- "DV"

    -- Выбор оператора
    country             VARCHAR(100),              -- "Саудовская Аравия"
    country_en          VARCHAR(100),              -- "Saudi Arabia"
    hotel               VARCHAR(255),
    remark              TEXT,

    -- Манифест
    manifest_filename   VARCHAR(255),

    -- Статус
    status              tour_status NOT NULL DEFAULT 'draft',

    -- Кто создал
    created_by          UUID REFERENCES users(id),

    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tours_status ON tours (status);
CREATE INDEX IF NOT EXISTS ix_tours_route  ON tours (route);


-- ── 3. pilgrims ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pilgrims (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    surname         VARCHAR(100) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    document        VARCHAR(50),                   -- c_doc_number
    package_name    VARCHAR(255),                  -- "17.02-24.02 NIYET"
    tour_code       VARCHAR(64),
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pilgrims_tour       ON pilgrims (tour_id);
CREATE INDEX IF NOT EXISTS ix_pilgrims_surname    ON pilgrims (surname);
CREATE INDEX IF NOT EXISTS ix_pilgrims_name       ON pilgrims (name);
CREATE INDEX IF NOT EXISTS ix_pilgrims_document   ON pilgrims (document);
CREATE INDEX IF NOT EXISTS ix_pilgrims_package    ON pilgrims (package_name);
CREATE INDEX IF NOT EXISTS ix_pilgrims_tour_code  ON pilgrims (tour_code);


-- ── 4. tour_offers (сегменты перелётов) ─────────────────

CREATE TABLE IF NOT EXISTS tour_offers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,

    offer_index     INTEGER NOT NULL DEFAULT 0,    -- 0, 1, 2…
    offer_type      VARCHAR(50) NOT NULL DEFAULT 'flight',
    date_from       VARCHAR(20),                   -- o_date_from_N
    date_to         VARCHAR(20),                   -- o_date_to_N
    airlines        VARCHAR(50),                   -- o_airlines_N
    airport         VARCHAR(10),                   -- o_airport_N
    country         VARCHAR(100),                  -- o_country_N

    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_to_tour ON tour_offers (tour_id);


-- ── 5. dispatch_jobs (outbox) ───────────────────────────

CREATE TABLE IF NOT EXISTS dispatch_jobs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tour_id             UUID REFERENCES tours(id) ON DELETE SET NULL,

    status              dispatch_job_status NOT NULL DEFAULT 'draft',

    payload             JSONB NOT NULL,
    prepared_payload    JSONB,
    response_payload    JSONB,

    attempt_count       INTEGER NOT NULL DEFAULT 0,
    max_attempts        INTEGER NOT NULL DEFAULT 5,
    next_attempt_at     TIMESTAMP,
    last_attempt_at     TIMESTAMP,
    sent_at             TIMESTAMP,

    celery_task_id      VARCHAR(128),
    error_message       TEXT,

    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dj_status   ON dispatch_jobs (status);
CREATE INDEX IF NOT EXISTS ix_dj_tour     ON dispatch_jobs (tour_id);
CREATE INDEX IF NOT EXISTS ix_dj_next     ON dispatch_jobs (next_attempt_at);
CREATE INDEX IF NOT EXISTS ix_dj_sent     ON dispatch_jobs (sent_at);
CREATE INDEX IF NOT EXISTS ix_dj_celery   ON dispatch_jobs (celery_task_id);


-- ── 6. audit_log ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email      VARCHAR(255),

    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,
    entity_id       UUID,

    old_data        JSONB,
    new_data        JSONB,

    ip_address      VARCHAR(45),
    user_agent      TEXT,

    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_al_user     ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS ix_al_action   ON audit_log (action);
CREATE INDEX IF NOT EXISTS ix_al_entity   ON audit_log (entity_type);
CREATE INDEX IF NOT EXISTS ix_al_eid      ON audit_log (entity_id);
CREATE INDEX IF NOT EXISTS ix_al_created  ON audit_log (created_at);


-- ── 7. system_settings ─────────────────────────────────

CREATE TABLE IF NOT EXISTS system_settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       JSONB NOT NULL,
    description TEXT,
    updated_at  TIMESTAMP DEFAULT now(),
    updated_by  UUID REFERENCES users(id)
);
