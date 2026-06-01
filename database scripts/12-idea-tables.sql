-- 12-idea-tables.sql
-- Idea entity (knowledge whiteboard)

-- =============================================================================
-- IDEA (master table)
-- =============================================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_i_idea
(
    idea_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idea_title        character varying(500) NOT NULL,
    idea_subtitle     character varying(500),
    idea_lang         character varying(2)   NOT NULL DEFAULT 'it',
    idea_body_delta   jsonb,                          -- NULL until whiteboard is edited
    idea_is_published boolean                NOT NULL DEFAULT false,
    usr_id            bigint                 NOT NULL,
    idea_created_at   timestamptz            NOT NULL DEFAULT now(),
    idea_updated_at   timestamptz            NOT NULL DEFAULT now()
);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================

ALTER TABLE nightsquirrel.tbl_i_idea
    ADD CONSTRAINT fk_tbl_i_idea_user
    FOREIGN KEY (usr_id) REFERENCES nightsquirrel.tbl_u_user (usr_id)
    ON DELETE RESTRICT;

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_tbl_i_idea_usr_id       ON nightsquirrel.tbl_i_idea (usr_id);
CREATE INDEX idx_tbl_i_idea_lang         ON nightsquirrel.tbl_i_idea (idea_lang);
CREATE INDEX idx_tbl_i_idea_is_published ON nightsquirrel.tbl_i_idea (idea_is_published);

-- =============================================================================
-- TRIGGER (updated_at — same pattern as all other tables)
-- =============================================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_i_idea_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.idea_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_i_idea_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_i_idea
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_i_idea_set_updated_at();

-- =============================================================================
-- JUNCTION: idea ↔ tag
-- =============================================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_i_idea2tag
(
    i2t_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idea_id bigint NOT NULL,
    tag_id  bigint NOT NULL,
    CONSTRAINT uq_tbl_i2t_idea_tag UNIQUE (idea_id, tag_id)
);

ALTER TABLE nightsquirrel.tbl_i_idea2tag
    ADD CONSTRAINT fk_tbl_i2t_idea
    FOREIGN KEY (idea_id) REFERENCES nightsquirrel.tbl_i_idea (idea_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_i_idea2tag
    ADD CONSTRAINT fk_tbl_i2t_tag
    FOREIGN KEY (tag_id)  REFERENCES nightsquirrel.tbl_t_tag  (tag_id)  ON DELETE CASCADE;

CREATE INDEX idx_tbl_i2t_idea_id ON nightsquirrel.tbl_i_idea2tag (idea_id);
CREATE INDEX idx_tbl_i2t_tag_id  ON nightsquirrel.tbl_i_idea2tag (tag_id);

-- =============================================================================
-- JUNCTION: idea ↔ reference
-- =============================================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_i_idea2reference
(
    i2r_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idea_id bigint NOT NULL,
    ref_id  bigint NOT NULL,
    CONSTRAINT uq_tbl_i2r_idea_ref UNIQUE (idea_id, ref_id)
);

ALTER TABLE nightsquirrel.tbl_i_idea2reference
    ADD CONSTRAINT fk_tbl_i2r_idea
    FOREIGN KEY (idea_id) REFERENCES nightsquirrel.tbl_i_idea     (idea_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_i_idea2reference
    ADD CONSTRAINT fk_tbl_i2r_ref
    FOREIGN KEY (ref_id)  REFERENCES nightsquirrel.tbl_r_reference (ref_id)  ON DELETE CASCADE;

CREATE INDEX idx_tbl_i2r_idea_id ON nightsquirrel.tbl_i_idea2reference (idea_id);
CREATE INDEX idx_tbl_i2r_ref_id  ON nightsquirrel.tbl_i_idea2reference (ref_id);

-- =============================================================================
-- JUNCTION: idea ↔ answer
-- =============================================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_i_idea2answer
(
    i2a_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idea_id bigint NOT NULL,
    ans_id  bigint NOT NULL,
    CONSTRAINT uq_tbl_i2a_idea_ans UNIQUE (idea_id, ans_id)
);

ALTER TABLE nightsquirrel.tbl_i_idea2answer
    ADD CONSTRAINT fk_tbl_i2a_idea
    FOREIGN KEY (idea_id) REFERENCES nightsquirrel.tbl_i_idea    (idea_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_i_idea2answer
    ADD CONSTRAINT fk_tbl_i2a_answer
    FOREIGN KEY (ans_id)  REFERENCES nightsquirrel.tbl_q_answer  (ans_id)  ON DELETE CASCADE;

CREATE INDEX idx_tbl_i2a_idea_id ON nightsquirrel.tbl_i_idea2answer (idea_id);
CREATE INDEX idx_tbl_i2a_ans_id  ON nightsquirrel.tbl_i_idea2answer (ans_id);
