
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- Для генерации UUID
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Для full-text search
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- Для поиска без учёта диакритики

CREATE TYPE user_role AS ENUM ('admin', 'manager', 'operator');

-- Статусы туров
CREATE TYPE tour_status AS ENUM (
    'draft',              -- Черновик
    'confirmed',          -- Подтверждён, готов к отправке
    'queued',            -- В очереди на отправку
    'processing',        -- Отправляется
    'submitted',         -- Успешно отправлен на госсайт
    'completed',         -- Полностью завершён
    'failed',            -- Ошибка отправки
    'cancelled'          -- Отменён
);

-- Типы туров
CREATE TYPE tour_type AS ENUM ('авиа', 'автобус', 'комбинированный');

-- Статусы паломников в туре
CREATE TYPE tour_pilgrim_status AS ENUM (
    'pending',           -- Ожидает отправки
    'submitted',         -- Отправлен на госсайт
    'confirmed',         -- Подтверждён госсайтом
    'rejected'           -- Отклонён
);

-- Откуда добавлен паломник
CREATE TYPE pilgrim_source AS ENUM ('manifest', 'manual', 'import');

-- Статусы Selenium задач
CREATE TYPE selenium_task_status AS ENUM (
    'pending',           -- Ожидает
    'processing',        -- Выполняется
    'success',           -- Успешно
    'failed',            -- Ошибка
    'retry'              -- Повтор
);

-- =====================================================
-- TABLE: users - Пользователи системы
-- =====================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'operator',
    is_active BOOLEAN DEFAULT TRUE,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,

    -- Индексы будут добавлены позже
    CONSTRAINT users_email_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

COMMENT ON TABLE users IS 'Пользователи системы (менеджеры, операторы, админы)';
COMMENT ON COLUMN users.role IS 'admin - полный доступ, manager - управление турами, operator - создание тур-кодов';

-- =====================================================
-- TABLE: pilgrims - База паломников
-- =====================================================

CREATE TABLE pilgrims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Личные данные
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    passport_number VARCHAR(50) UNIQUE NOT NULL,

    -- Дополнительная информация
    date_of_birth DATE,
    phone VARCHAR(50),
    email VARCHAR(255),

    -- Менеджер, который работает с паломником
    manager VARCHAR(100),

    -- Заметки
    notes TEXT,

    -- Поле для full-text search (автоматически обновляется)
    full_name_search TSVECTOR,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ограничения
    CONSTRAINT pilgrims_passport_format CHECK (
        passport_number ~ '^[A-Z]{1,2}[0-9]{7,9}$' OR
        passport_number ~ '^[0-9]{9}$'
    )
);

COMMENT ON TABLE pilgrims IS 'База всех паломников - центральная таблица с данными о людях';
COMMENT ON COLUMN pilgrims.passport_number IS 'Формат: N1234567 или 123456789';
COMMENT ON COLUMN pilgrims.manager IS 'Менеджер компании (Алия Касымова, Нурлан Абаев и т.д.)';
COMMENT ON COLUMN pilgrims.full_name_search IS 'Автоматически генерируемое поле для быстрого поиска';

-- Триггер для автоматического обновления full_name_search
CREATE OR REPLACE FUNCTION update_pilgrim_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.full_name_search :=
        setweight(to_tsvector('russian', COALESCE(NEW.last_name, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.first_name, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.middle_name, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.passport_number, '')), 'C');
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pilgrims_search_vector_update
    BEFORE INSERT OR UPDATE ON pilgrims
    FOR EACH ROW
    EXECUTE FUNCTION update_pilgrim_search_vector();

-- =====================================================
-- TABLE: hotels - Отели
-- =====================================================

CREATE TABLE hotels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,           -- Makkah, Madinah
    country VARCHAR(100) NOT NULL DEFAULT 'Saudi Arabia',
    stars INTEGER CHECK (stars >= 1 AND stars <= 5),
    address TEXT,
    distance_to_haram INTEGER,            -- Метры до Харама

    -- Дополнительная информация
    description TEXT,
    amenities JSONB,                      -- {"wifi": true, "breakfast": true}

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE hotels IS 'Отели для размещения паломников';
COMMENT ON COLUMN hotels.distance_to_haram IS 'Расстояние до Харама в метрах';

-- =====================================================
-- TABLE: flights - Рейсы
-- =====================================================

CREATE TABLE flights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route VARCHAR(50) UNIQUE NOT NULL,    -- ALA-JED, NQZ-MED
    departure_city VARCHAR(100) NOT NULL,  -- Almaty, Nur-Sultan
    arrival_city VARCHAR(100) NOT NULL,    -- Jeddah, Medina
    airline VARCHAR(100),

    -- Дополнительная информация
    flight_number VARCHAR(20),
    duration_hours INTEGER,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT flights_route_format CHECK (route ~ '^[A-Z]{3}-[A-Z]{3}$')
);

COMMENT ON TABLE flights IS 'Авиарейсы для паломнических туров';
COMMENT ON COLUMN flights.route IS 'Формат: ALA-JED (3-буквенные IATA коды)';

-- =====================================================
-- TABLE: tours - Основная таблица туров
-- =====================================================

CREATE TABLE tours (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Основная информация
    date_short VARCHAR(10),                -- "17.02" для быстрого поиска
    date_start DATE NOT NULL,
    date_end DATE NOT NULL,
    days INTEGER NOT NULL,

    -- Маршрут и тип
    route VARCHAR(50),                     -- ALA-JED, NQZ-MED
    type tour_type DEFAULT 'авиа',

    -- Связи
    hotel_id UUID REFERENCES hotels(id) ON DELETE SET NULL,
    flight_id UUID REFERENCES flights(id) ON DELETE SET NULL,

    -- Статус
    status tour_status DEFAULT 'draft',

    -- Связь с Google Sheets
    google_sheet_name VARCHAR(100),        -- "17.02.2026"
    google_sheet_url TEXT,

    -- Загруженный манифест
    manifest_file_path TEXT,
    manifest_original_filename VARCHAR(255),

    -- Данные о создателе
    created_by UUID REFERENCES users(id),

    -- Метаданные отправки на госсайт
    gov_submission_id VARCHAR(100),        -- Номер заявки на госсайте (#12345)
    gov_site_response TEXT,                -- Полный ответ от госсайта
    screenshot_path TEXT,                  -- Путь к скриншоту результата

    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,                -- Когда подтвердили (ввели "yes")
    submitted_at TIMESTAMP,                -- Когда отправили на госсайт

    -- Ограничения
    CONSTRAINT tours_dates_check CHECK (date_end > date_start),
    CONSTRAINT tours_days_check CHECK (days > 0 AND days <= 30)
);

COMMENT ON TABLE tours IS 'Туры (тур-коды) - основная сущность системы';
COMMENT ON COLUMN tours.date_short IS 'Короткая дата для удобного поиска (17.02)';
COMMENT ON COLUMN tours.gov_submission_id IS 'ID заявки на государственном сайте';

-- Триггер для автоматического расчёта количества дней
CREATE OR REPLACE FUNCTION calculate_tour_days()
RETURNS TRIGGER AS $$
BEGIN
    NEW.days := (NEW.date_end - NEW.date_start) + 1;
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tours_calculate_days
    BEFORE INSERT OR UPDATE OF date_start, date_end ON tours
    FOR EACH ROW
    EXECUTE FUNCTION calculate_tour_days();

-- =====================================================
-- TABLE: tour_pilgrims - Связь туров и паломников
-- =====================================================

CREATE TABLE tour_pilgrims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Связи
    tour_id UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    pilgrim_id UUID NOT NULL REFERENCES pilgrims(id) ON DELETE CASCADE,

    -- Данные на момент добавления в тур
    flight_date DATE,

    -- Откуда был добавлен паломник
    added_from pilgrim_source DEFAULT 'manifest',

    -- Статус паломника в этом туре
    status tour_pilgrim_status DEFAULT 'pending',

    -- Метаданные
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by UUID REFERENCES users(id),

    -- Уникальность: один паломник может быть только один раз в одном туре
    CONSTRAINT tour_pilgrims_unique UNIQUE (tour_id, pilgrim_id)
);

COMMENT ON TABLE tour_pilgrims IS 'Связь между турами и паломниками (many-to-many)';
COMMENT ON COLUMN tour_pilgrims.added_from IS 'manifest - из манифеста, manual - вручную, import - импорт';

-- =====================================================
-- TABLE: manifest_validations - История валидаций манифестов
-- =====================================================

CREATE TABLE manifest_validations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Связь с туром
    tour_id UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,

    -- Статистика парсинга
    total_in_manifest INTEGER NOT NULL,
    matched_count INTEGER NOT NULL,
    missing_in_db_count INTEGER NOT NULL,
    missing_in_manifest_count INTEGER NOT NULL,
    errors_count INTEGER DEFAULT 0,

    -- Детальные данные (JSON)
    missing_in_db JSONB,           -- [{last_name, first_name, passport, ...}]
    missing_in_manifest JSONB,     -- [{pilgrim_id, last_name, ...}]
    errors JSONB,                  -- [{row, error_message, ...}]

    -- Метаданные
    validated_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE manifest_validations IS 'История валидаций загруженных манифестов';
COMMENT ON COLUMN manifest_validations.missing_in_db IS 'Паломники которые есть в манифесте, но отсутствуют в БД';
COMMENT ON COLUMN manifest_validations.missing_in_manifest IS 'Паломники которые есть в БД, но отсутствуют в манифесте';

-- =====================================================
-- TABLE: selenium_tasks - Задачи для Selenium Worker
-- =====================================================

CREATE TABLE selenium_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Связь с туром
    tour_id UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,

    -- Статус задачи
    status selenium_task_status DEFAULT 'pending',

    -- Прогресс выполнения
    progress JSONB,                -- {current_step, completed, total, percentage}

    -- Временные метки
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Результат выполнения
    result JSONB,                  -- {success, submission_id, screenshot_url}
    error_message TEXT,
    error_details JSONB,

    -- Retry логика
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT selenium_tasks_retry_check CHECK (retry_count <= max_retries)
);

COMMENT ON TABLE selenium_tasks IS 'Задачи для отправки туров на госсайт через Selenium';
COMMENT ON COLUMN selenium_tasks.progress IS 'Текущий прогресс: {current_step: "Добавление паломников", completed: 25, total: 42}';

-- =====================================================
-- TABLE: audit_log - Журнал всех действий
-- =====================================================

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Кто совершил действие
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email VARCHAR(255),

    -- Что было сделано
    action VARCHAR(100) NOT NULL,         -- create_tour, upload_manifest, etc.
    entity_type VARCHAR(50) NOT NULL,     -- tour, pilgrim, user
    entity_id UUID,

    -- Данные до и после (для отслеживания изменений)
    old_data JSONB,
    new_data JSONB,

    -- Дополнительная информация
    ip_address INET,
    user_agent TEXT,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE audit_log IS 'Полный журнал всех действий в системе для аудита';

-- =====================================================
-- TABLE: system_settings - Настройки системы
-- =====================================================

CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id)
);

COMMENT ON TABLE system_settings IS 'Глобальные настройки системы (API ключи, лимиты и т.д.)';

-- =====================================================
-- INDEXES - Индексы для оптимизации запросов
-- =====================================================

-- Users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

-- Pilgrims - КРИТИЧНО для производительности!
CREATE INDEX idx_pilgrims_passport ON pilgrims(passport_number);
CREATE INDEX idx_pilgrims_last_name ON pilgrims(last_name);
CREATE INDEX idx_pilgrims_first_name ON pilgrims(first_name);
CREATE INDEX idx_pilgrims_manager ON pilgrims(manager);
CREATE INDEX idx_pilgrims_created ON pilgrims(created_at DESC);

-- Full-text search индекс (очень важно!)
CREATE INDEX idx_pilgrims_search ON pilgrims USING GIN(full_name_search);

-- Для поиска по частичному совпадению (LIKE '%name%')
CREATE INDEX idx_pilgrims_last_name_trgm ON pilgrims USING GIN(last_name gin_trgm_ops);
CREATE INDEX idx_pilgrims_first_name_trgm ON pilgrims USING GIN(first_name gin_trgm_ops);

-- Tours - Часто используемые фильтры
CREATE INDEX idx_tours_date_start ON tours(date_start);
CREATE INDEX idx_tours_date_end ON tours(date_end);
CREATE INDEX idx_tours_date_short ON tours(date_short);
CREATE INDEX idx_tours_status ON tours(status);
CREATE INDEX idx_tours_route ON tours(route);
CREATE INDEX idx_tours_type ON tours(type);
CREATE INDEX idx_tours_created_by ON tours(created_by);
CREATE INDEX idx_tours_created_at ON tours(created_at DESC);

-- Composite индекс для частых запросов
CREATE INDEX idx_tours_status_date ON tours(status, date_start DESC);

-- Tour Pilgrims
CREATE INDEX idx_tour_pilgrims_tour ON tour_pilgrims(tour_id);
CREATE INDEX idx_tour_pilgrims_pilgrim ON tour_pilgrims(pilgrim_id);
CREATE INDEX idx_tour_pilgrims_status ON tour_pilgrims(status);
CREATE INDEX idx_tour_pilgrims_added_at ON tour_pilgrims(added_at DESC);

-- Manifest Validations
CREATE INDEX idx_manifest_validations_tour ON manifest_validations(tour_id);
CREATE INDEX idx_manifest_validations_created ON manifest_validations(created_at DESC);

-- Selenium Tasks
CREATE INDEX idx_selenium_tasks_status ON selenium_tasks(status);
CREATE INDEX idx_selenium_tasks_tour ON selenium_tasks(tour_id);
CREATE INDEX idx_selenium_tasks_created ON selenium_tasks(created_at DESC);
CREATE INDEX idx_selenium_tasks_pending ON selenium_tasks(status) WHERE status = 'pending';

-- Audit Log
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- Hotels & Flights
CREATE INDEX idx_hotels_city ON hotels(city);
CREATE INDEX idx_hotels_is_active ON hotels(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_flights_route ON flights(route);
CREATE INDEX idx_flights_is_active ON flights(is_active) WHERE is_active = TRUE;

-- =====================================================
-- VIEWS - Представления для удобных запросов
-- =====================================================

-- Детальная информация о турах
CREATE VIEW v_tours_detailed AS
SELECT
    t.*,
    h.name as hotel_name,
    h.city as hotel_city,
    h.stars as hotel_stars,
    f.route as flight_route,
    f.airline as flight_airline,
    u.full_name as created_by_name,
    u.email as created_by_email,
    COUNT(DISTINCT tp.id) as pilgrims_count,
    COUNT(DISTINCT tp.id) FILTER (WHERE tp.status = 'submitted') as submitted_count,
    st.status as selenium_status
FROM tours t
LEFT JOIN hotels h ON t.hotel_id = h.id
LEFT JOIN flights f ON t.flight_id = f.id
LEFT JOIN users u ON t.created_by = u.id
LEFT JOIN tour_pilgrims tp ON t.id = tp.tour_id
LEFT JOIN selenium_tasks st ON t.id = st.tour_id
GROUP BY t.id, h.id, f.id, u.id, st.id;

COMMENT ON VIEW v_tours_detailed IS 'Детальная информация о турах со всеми связанными данными';

-- Статистика по паломникам
CREATE VIEW v_pilgrims_stats AS
SELECT
    p.*,
    COUNT(DISTINCT tp.tour_id) as tours_count,
    MAX(tp.added_at) as last_tour_date,
    ARRAY_AGG(DISTINCT t.route) FILTER (WHERE t.route IS NOT NULL) as routes_history
FROM pilgrims p
LEFT JOIN tour_pilgrims tp ON p.id = tp.pilgrim_id
LEFT JOIN tours t ON tp.tour_id = t.id
GROUP BY p.id;

COMMENT ON VIEW v_pilgrims_stats IS 'Статистика по каждому паломнику (сколько туров, когда последний)';

-- =====================================================
-- FUNCTIONS - Полезные функции
-- =====================================================

-- Функция для поиска паломников (с ранжированием)
CREATE OR REPLACE FUNCTION search_pilgrims(search_query TEXT)
RETURNS TABLE (
    id UUID,
    last_name VARCHAR,
    first_name VARCHAR,
    middle_name VARCHAR,
    passport_number VARCHAR,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.last_name,
        p.first_name,
        p.middle_name,
        p.passport_number,
        ts_rank(p.full_name_search, plainto_tsquery('russian', search_query)) as rank
    FROM pilgrims p
    WHERE p.full_name_search @@ plainto_tsquery('russian', search_query)
       OR p.passport_number ILIKE '%' || search_query || '%'
    ORDER BY rank DESC, p.last_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_pilgrims IS 'Полнотекстовый поиск паломников с ранжированием результатов';

-- Функция для получения статистики дашборда
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'total_tours', (SELECT COUNT(*) FROM tours),
        'active_tours', (SELECT COUNT(*) FROM tours WHERE status IN ('confirmed', 'submitted')),
        'total_pilgrims', (SELECT COUNT(*) FROM pilgrims),
        'active_pilgrims', (
            SELECT COUNT(DISTINCT pilgrim_id)
            FROM tour_pilgrims tp
            JOIN tours t ON tp.tour_id = t.id
            WHERE t.status IN ('confirmed', 'submitted')
        ),
        'pending_tasks', (SELECT COUNT(*) FROM selenium_tasks WHERE status = 'pending'),
        'failed_tasks', (SELECT COUNT(*) FROM selenium_tasks WHERE status = 'failed')
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_dashboard_stats IS 'Получить статистику для главного дашборда';

-- =====================================================
-- SEED DATA - Начальные данные
-- =====================================================

-- Создаём администратора по умолчанию
-- Пароль: admin123 (хеш будет сгенерирован в приложении)
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'admin@hickmet.kz',
    '$2b$12$placeholder_hash',  -- Будет заменён при первом запуске
    'Системный администратор',
    'admin'
);

-- Добавляем тестовые отели
INSERT INTO hotels (name, city, country, stars, distance_to_haram) VALUES
('Hilton Makkah Convention Hotel', 'Makkah', 'Saudi Arabia', 5, 500),
('Swissotel Makkah', 'Makkah', 'Saudi Arabia', 5, 300),
('Pullman ZamZam Makkah', 'Makkah', 'Saudi Arabia', 5, 100),
('Fairmont Makkah Clock Royal Tower', 'Makkah', 'Saudi Arabia', 5, 50),
('Millennium Al Aqeeq Hotel', 'Madinah', 'Saudi Arabia', 4, 200);

-- Добавляем рейсы
INSERT INTO flights (route, departure_city, arrival_city, airline) VALUES
('ALA-JED', 'Almaty', 'Jeddah', 'Air Astana'),
('ALA-MED', 'Almaty', 'Medina', 'Air Astana'),
('NQZ-JED', 'Nur-Sultan', 'Jeddah', 'SCAT Airlines'),
('NQZ-MED', 'Nur-Sultan', 'Medina', 'SCAT Airlines'),
('NQZ-ALA', 'Nur-Sultan', 'Almaty', 'Air Astana');

-- Системные настройки
INSERT INTO system_settings (key, value, description) VALUES
('max_pilgrims_per_tour', '50', 'Максимальное количество паломников в одном туре'),
('manifest_auto_parse', 'true', 'Автоматически парсить манифест после загрузки'),
('selenium_timeout_seconds', '300', 'Таймаут для Selenium операций'),
('notification_email', '"admin@hickmet.kz"', 'Email для уведомлений');

-- =====================================================
-- GRANTS - Права доступа
-- =====================================================

-- Создаём роли для приложения
-- (Выполните это на проде с правильными паролями!)

-- CREATE ROLE hickmet_app WITH LOGIN PASSWORD 'secure_password_here';
-- GRANT CONNECT ON DATABASE hickmet TO hickmet_app;
-- GRANT USAGE ON SCHEMA public TO hickmet_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hickmet_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hickmet_app;

-- =====================================================
-- КОНЕЦ СХЕМЫ
-- =====================================================

-- Проверка версии схемы
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT INTO schema_version (version, description) VALUES
(1, 'Initial schema - полная структура БД для Hickmet Premium');

-- Вывести статистику
SELECT
    'Tables created: ' || COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

SELECT
    'Indexes created: ' || COUNT(*)
FROM pg_indexes
WHERE schemaname = 'public';
