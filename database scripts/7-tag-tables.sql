-- 7-tag-tables.sql
-- Tags and tag junction entities

-- ─────────────────────────────────────────────────────────────────────────────
-- TAG (master table)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_t_tag
(
    tag_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_name_ita   character varying(250) NOT NULL,
    tag_name_eng   character varying(250) NOT NULL,
    tag_type       character varying(64),          -- optional classifier / safety net
    tag_icon       character varying(125),         -- icon path in static folder
    tag_created_at timestamptz NOT NULL DEFAULT now(),
    tag_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_tbl_t_tag_name_ita UNIQUE (tag_name_ita),
    CONSTRAINT uq_tbl_t_tag_name_eng UNIQUE (tag_name_eng)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- JUNCTION: tag ↔ question
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_t_tag2question
(
    t2q_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_id    bigint  NOT NULL,
    qtn_id    bigint  NOT NULL,
    t2q_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_tbl_t2q_tag_qtn UNIQUE (tag_id, qtn_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- JUNCTION: tag ↔ reference
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_t_tag2reference
(
    t2r_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_id    bigint  NOT NULL,
    ref_id    bigint  NOT NULL,
    t2r_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_tbl_t2r_tag_ref UNIQUE (tag_id, ref_id)
);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================

-- tag2question → tag and question (CASCADE: detach automatically when either side is deleted)
ALTER TABLE nightsquirrel.tbl_t_tag2question ADD CONSTRAINT fk_tbl_t2q_tag
    FOREIGN KEY (tag_id) REFERENCES nightsquirrel.tbl_t_tag      (tag_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_t_tag2question ADD CONSTRAINT fk_tbl_t2q_question
    FOREIGN KEY (qtn_id) REFERENCES nightsquirrel.tbl_q_question (qtn_id) ON DELETE CASCADE;

-- tag2reference → tag and reference (CASCADE: same rationale)
ALTER TABLE nightsquirrel.tbl_t_tag2reference ADD CONSTRAINT fk_tbl_t2r_tag
    FOREIGN KEY (tag_id) REFERENCES nightsquirrel.tbl_t_tag       (tag_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_t_tag2reference ADD CONSTRAINT fk_tbl_t2r_reference
    FOREIGN KEY (ref_id) REFERENCES nightsquirrel.tbl_r_reference  (ref_id) ON DELETE CASCADE;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Tag name search
CREATE INDEX idx_tbl_t_tag_name_ita ON nightsquirrel.tbl_t_tag (tag_name_ita);
CREATE INDEX idx_tbl_t_tag_name_eng ON nightsquirrel.tbl_t_tag (tag_name_eng);

-- tag2question: UNIQUE on (tag_id, qtn_id) already covers the tag→questions direction;
-- add an index on qtn_id alone for the "all tags on this question" query
CREATE INDEX idx_tbl_t2q_qtn_id ON nightsquirrel.tbl_t_tag2question (qtn_id);

-- tag2reference: same pattern
CREATE INDEX idx_tbl_t2r_ref_id ON nightsquirrel.tbl_t_tag2reference (ref_id);

-- =============================================================================
-- TRIGGERS (updated_at — same pattern as all other tables)
-- =============================================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_t_tag_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.tag_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_t_tag_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_t_tag
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_t_tag_set_updated_at();
