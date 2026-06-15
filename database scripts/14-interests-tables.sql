-- 14-interests-tables.sql
-- User interests and junction entities

-- ─────────────────────────────────────────────────────────────────────────────
-- INTEREST (master table)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_u_interest
(
    uit_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uit_name_ita   character varying(250) NOT NULL,
    uit_name_eng   character varying(250) NOT NULL,
    uit_type       character varying(64),          -- optional classifier / broad area
    uit_created_at timestamptz NOT NULL DEFAULT now(),
    uit_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_tbl_u_interest_name_ita UNIQUE (uit_name_ita),
    CONSTRAINT uq_tbl_u_interest_name_eng UNIQUE (uit_name_eng)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- JUNCTION: interest ↔ user
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_u_interest2user
(
    i2u_id    bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uit_id    bigint  NOT NULL,
    usr_id    bigint  NOT NULL,
    i2u_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_tbl_i2u_interest_user UNIQUE (uit_id, usr_id)
);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================

-- interest2user → interest (CASCADE: removing an interest detaches it from all users)
ALTER TABLE nightsquirrel.tbl_u_interest2user ADD CONSTRAINT fk_tbl_i2u_interest
    FOREIGN KEY (uit_id) REFERENCES nightsquirrel.tbl_u_interest (uit_id) ON DELETE CASCADE;

-- interest2user → user (CASCADE: removing a user removes their interest links)
ALTER TABLE nightsquirrel.tbl_u_interest2user ADD CONSTRAINT fk_tbl_i2u_user
    FOREIGN KEY (usr_id) REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE CASCADE;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Interest name search (used for autocomplete / pick-list)
CREATE INDEX idx_tbl_u_interest_name_ita ON nightsquirrel.tbl_u_interest (uit_name_ita);
CREATE INDEX idx_tbl_u_interest_name_eng ON nightsquirrel.tbl_u_interest (uit_name_eng);

-- interest2user: UNIQUE on (uit_id, usr_id) already covers the interest→users direction;
-- add an index on usr_id alone for the "all interests of this user" query
CREATE INDEX idx_tbl_i2u_usr_id ON nightsquirrel.tbl_u_interest2user (usr_id);

-- =============================================================================
-- TRIGGERS (updated_at — same pattern as all other tables)
-- =============================================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_u_interest_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.uit_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_u_interest_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_u_interest
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_u_interest_set_updated_at();
