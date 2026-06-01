-- 6-reference-tables.sql
-- References and related entities

-- ─────────────────────────────────────────────────────────────────────────────
-- REFERENCE TYPE (lookup)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_reference_type
(
    rtp_id       bigint                 PRIMARY KEY,
    rtp_name_ita character varying(250) NOT NULL,
    rtp_name_eng character varying(250) NOT NULL,
    rtp_seqno    integer                NOT NULL
);

INSERT INTO nightsquirrel.tbl_r_reference_type VALUES (1, 'Libro',    'Book',     1);
INSERT INTO nightsquirrel.tbl_r_reference_type VALUES (2, 'Articolo', 'Paper',    2);
INSERT INTO nightsquirrel.tbl_r_reference_type VALUES (3, 'Video',    'Video',    3);
INSERT INTO nightsquirrel.tbl_r_reference_type VALUES (4, 'Web Link', 'Web Link', 4);

-- ─────────────────────────────────────────────────────────────────────────────
-- PERSON (authors, editors, translators)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_person
(
    per_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    per_firstname  character varying(256),
    per_familyname character varying(256),
    per_caption_ita character varying(512),
    per_caption_eng character varying(512),
    per_strings    character varying(512),    -- alternate names / search tokens
    per_won_nobel  VARCHAR(256),
    per_created_at timestamptz NOT NULL DEFAULT now(),
    per_updated_at timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- PUBLISHER
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_publisher
(
    pub_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pub_name        character varying(512)  NOT NULL,
    pub_othername   character varying(512),
    pub_location    character varying(512),
    pub_description character varying(1024),
    pub_created_at  timestamptz NOT NULL DEFAULT now(),
    pub_updated_at  timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- IMAGE (cover / thumbnail images for references, stored in S3)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_image
(
    img_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    img_filename     character varying(255) NOT NULL,
    img_s3_key       character varying(512) NOT NULL,
    img_content_type character varying(100) NOT NULL,
    img_size_bytes   bigint                 NOT NULL,
    img_created_at   timestamptz            NOT NULL DEFAULT now(),
    CONSTRAINT uq_tbl_r_image_s3_key UNIQUE (img_s3_key)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- BOOK
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_book
(
    bok_id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bok_author1_per_id     bigint,
    bok_author2_per_id     bigint,
    bok_author_other       character varying(1024),
    bok_author_etal        boolean NOT NULL DEFAULT false,
    bok_title              character varying(1024),
    bok_subtitle           character varying(1024),
    bok_editor1_per_id     bigint,
    bok_editor2_per_id     bigint,
    bok_editor_other       character varying(1024),
    bok_editor_etal        boolean NOT NULL DEFAULT false,
    bok_translator1_per_id bigint,
    bok_translator2_per_id bigint,
    bok_translator_other   character varying(1024),
    bok_translator_etal    boolean NOT NULL DEFAULT false,
    bok_year               integer,
    pub_id                 bigint,
    bok_location           character varying(512),
    bok_isbn               character varying(20),
    bok_edition            character varying(120),
    bok_language           character varying(20),
    bok_pages              integer,
    bok_link               character varying(1024),
    usr_id                 bigint NOT NULL,
    bok_created_at         timestamptz NOT NULL DEFAULT now(),
    bok_updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_tbl_r_book_year CHECK (bok_year IS NULL OR bok_year BETWEEN 1000 AND 2200)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ARTICLE / PAPER
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_article
(
    art_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    art_author1_per_id bigint,
    art_author2_per_id bigint,
    art_author_other   character varying(1024),
    art_author_etal    boolean NOT NULL DEFAULT false,
    art_title          character varying(1024),
    art_editor1_per_id bigint,
    art_editor2_per_id bigint,
    art_editor_other   character varying(1024),
    art_editor_etal    boolean NOT NULL DEFAULT false,
    art_date           character varying(8),     -- YYYY or YYYYMMDD partial date
    pub_id             bigint,
    art_location       character varying(512),
    art_doi            character varying(250),
    art_container      character varying(512),   -- journal / book series title
    art_issue          character varying(120),
    art_language       character varying(20),
    art_link           character varying(1024),
    usr_id             bigint NOT NULL,
    art_created_at     timestamptz NOT NULL DEFAULT now(),
    art_updated_at     timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- VIDEO
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_video
(
    vid_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vid_title      character varying(1024),
    vid_editor     character varying(1024),
    vid_date       character varying(8),
    vid_platform   character varying(512),
    vid_language   character varying(20),
    vid_link       character varying(1024),
    usr_id         bigint NOT NULL,
    vid_created_at timestamptz NOT NULL DEFAULT now(),
    vid_updated_at timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- WEB LINK
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_weblink
(
    wlk_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wlk_title      character varying(1024),
    wlk_editor     character varying(1024),
    wlk_date       character varying(8),
    wlk_platform   character varying(512),
    wlk_language   character varying(20),
    wlk_link       character varying(1024),
    usr_id         bigint NOT NULL,
    wlk_created_at timestamptz NOT NULL DEFAULT now(),
    wlk_updated_at timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- REFERENCE (top-level entity)
-- The draft's polymorphic ref_related_entity_id is replaced with four typed
-- nullable FK columns. Exactly one must be non-null (enforced by CHECK).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_reference
(
    ref_id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rtp_id               bigint NOT NULL,
    usr_id               bigint NOT NULL,
    ref_bok_id           bigint,
    ref_art_id           bigint,
    ref_vid_id           bigint,
    ref_wlk_id           bigint,
    ref_cover_img_id     bigint,
    ref_thumbnail_img_id bigint,
    ref_is_library       boolean     NOT NULL DEFAULT false,  -- true = part of admin's public library (Leo's book wall)
    ref_note             text,                                -- admin's personal recommendation / annotation
    ref_needs_review     boolean     NOT NULL DEFAULT false,  -- true if automatic info retrival fails
    ref_is_current       boolean     NOT NULL DEFAULT false,                                                                                              
    ref_is_recent        boolean     NOT NULL DEFAULT false,                                                                                              
    ref_is_crucial       boolean     NOT NULL DEFAULT false,
    ref_created_at       timestamptz NOT NULL DEFAULT now(),
    ref_updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_tbl_r_reference_single_entity CHECK (
        (CASE WHEN ref_bok_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN ref_art_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN ref_vid_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN ref_wlk_id IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

-- ─────────────────────────────────────────────────────────────────────────────
-- JUNCTION: reference ↔ question
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_reference2question
(
    r2q_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref_id    bigint  NOT NULL,
    qtn_id    bigint  NOT NULL,
    r2q_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_tbl_r2q_ref_qtn UNIQUE (ref_id, qtn_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- JUNCTION: reference ↔ answer
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_reference2answer
(
    r2a_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref_id    bigint  NOT NULL,
    ans_id    bigint  NOT NULL,
    r2a_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_tbl_r2a_ref_ans UNIQUE (ref_id, ans_id)
);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================

-- Book → Person (authors / editors / translators, SET NULL on person delete)
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_author1
    FOREIGN KEY (bok_author1_per_id)     REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_author2
    FOREIGN KEY (bok_author2_per_id)     REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_editor1
    FOREIGN KEY (bok_editor1_per_id)     REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_editor2
    FOREIGN KEY (bok_editor2_per_id)     REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_translator1
    FOREIGN KEY (bok_translator1_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_translator2
    FOREIGN KEY (bok_translator2_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_publisher
    FOREIGN KEY (pub_id)                 REFERENCES nightsquirrel.tbl_r_publisher (pub_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_book ADD CONSTRAINT fk_tbl_r_book_usr
    FOREIGN KEY (usr_id)                 REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE RESTRICT;

-- Article → Person / Publisher / User
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_author1
    FOREIGN KEY (art_author1_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_author2
    FOREIGN KEY (art_author2_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_editor1
    FOREIGN KEY (art_editor1_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_editor2
    FOREIGN KEY (art_editor2_per_id) REFERENCES nightsquirrel.tbl_r_person (per_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_publisher
    FOREIGN KEY (pub_id)             REFERENCES nightsquirrel.tbl_r_publisher (pub_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_article ADD CONSTRAINT fk_tbl_r_article_usr
    FOREIGN KEY (usr_id)             REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE RESTRICT;

-- Video / Weblink → User
ALTER TABLE nightsquirrel.tbl_r_video   ADD CONSTRAINT fk_tbl_r_video_usr
    FOREIGN KEY (usr_id) REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE RESTRICT;
ALTER TABLE nightsquirrel.tbl_r_weblink ADD CONSTRAINT fk_tbl_r_weblink_usr
    FOREIGN KEY (usr_id) REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE RESTRICT;

-- Reference → type, user, typed entities, images
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_type
    FOREIGN KEY (rtp_id)     REFERENCES nightsquirrel.tbl_r_reference_type (rtp_id);
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_usr
    FOREIGN KEY (usr_id)     REFERENCES nightsquirrel.tbl_u_user (usr_id) ON DELETE RESTRICT;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_book
    FOREIGN KEY (ref_bok_id) REFERENCES nightsquirrel.tbl_r_book    (bok_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_article
    FOREIGN KEY (ref_art_id) REFERENCES nightsquirrel.tbl_r_article (art_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_video
    FOREIGN KEY (ref_vid_id) REFERENCES nightsquirrel.tbl_r_video   (vid_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_weblink
    FOREIGN KEY (ref_wlk_id) REFERENCES nightsquirrel.tbl_r_weblink (wlk_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_cover_img
    FOREIGN KEY (ref_cover_img_id)     REFERENCES nightsquirrel.tbl_r_image (img_id) ON DELETE SET NULL;
ALTER TABLE nightsquirrel.tbl_r_reference ADD CONSTRAINT fk_tbl_r_reference_thumbnail_img
    FOREIGN KEY (ref_thumbnail_img_id) REFERENCES nightsquirrel.tbl_r_image (img_id) ON DELETE SET NULL;

-- Junction tables → reference / question / answer (all CASCADE)
ALTER TABLE nightsquirrel.tbl_r_reference2question ADD CONSTRAINT fk_tbl_r2q_reference
    FOREIGN KEY (ref_id) REFERENCES nightsquirrel.tbl_r_reference (ref_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference2question ADD CONSTRAINT fk_tbl_r2q_question
    FOREIGN KEY (qtn_id) REFERENCES nightsquirrel.tbl_q_question  (qtn_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference2answer   ADD CONSTRAINT fk_tbl_r2a_reference
    FOREIGN KEY (ref_id) REFERENCES nightsquirrel.tbl_r_reference (ref_id) ON DELETE CASCADE;
ALTER TABLE nightsquirrel.tbl_r_reference2answer   ADD CONSTRAINT fk_tbl_r2a_answer
    FOREIGN KEY (ans_id) REFERENCES nightsquirrel.tbl_q_answer    (ans_id) ON DELETE CASCADE;

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_tbl_r_person_familyname    ON nightsquirrel.tbl_r_person    (per_familyname);
CREATE INDEX idx_tbl_r_publisher_name       ON nightsquirrel.tbl_r_publisher (pub_name);

CREATE INDEX idx_tbl_r_book_author1         ON nightsquirrel.tbl_r_book (bok_author1_per_id);
CREATE INDEX idx_tbl_r_book_author2         ON nightsquirrel.tbl_r_book (bok_author2_per_id);
CREATE INDEX idx_tbl_r_book_editor1         ON nightsquirrel.tbl_r_book (bok_editor1_per_id);
CREATE INDEX idx_tbl_r_book_editor2         ON nightsquirrel.tbl_r_book (bok_editor2_per_id);
CREATE INDEX idx_tbl_r_book_pub_id          ON nightsquirrel.tbl_r_book (pub_id);
CREATE INDEX idx_tbl_r_book_usr_id          ON nightsquirrel.tbl_r_book (usr_id);

CREATE INDEX idx_tbl_r_article_author1      ON nightsquirrel.tbl_r_article (art_author1_per_id);
CREATE INDEX idx_tbl_r_article_author2      ON nightsquirrel.tbl_r_article (art_author2_per_id);
CREATE INDEX idx_tbl_r_article_pub_id       ON nightsquirrel.tbl_r_article (pub_id);
CREATE INDEX idx_tbl_r_article_usr_id       ON nightsquirrel.tbl_r_article (usr_id);

CREATE INDEX idx_tbl_r_video_usr_id         ON nightsquirrel.tbl_r_video   (usr_id);
CREATE INDEX idx_tbl_r_weblink_usr_id       ON nightsquirrel.tbl_r_weblink (usr_id);

CREATE INDEX idx_tbl_r_reference_rtp_id     ON nightsquirrel.tbl_r_reference (rtp_id);
CREATE INDEX idx_tbl_r_reference_usr_id     ON nightsquirrel.tbl_r_reference (usr_id);
CREATE INDEX idx_tbl_r_reference_is_library ON nightsquirrel.tbl_r_reference (ref_is_library);
CREATE INDEX idx_tbl_r_reference_created_at ON nightsquirrel.tbl_r_reference (ref_created_at DESC);
CREATE INDEX idx_tbl_r_reference_bok_id     ON nightsquirrel.tbl_r_reference (ref_bok_id);
CREATE INDEX idx_tbl_r_reference_art_id     ON nightsquirrel.tbl_r_reference (ref_art_id);
CREATE INDEX idx_tbl_r_reference_vid_id     ON nightsquirrel.tbl_r_reference (ref_vid_id);
CREATE INDEX idx_tbl_r_reference_wlk_id     ON nightsquirrel.tbl_r_reference (ref_wlk_id);

CREATE INDEX idx_tbl_r2q_ref_id             ON nightsquirrel.tbl_r_reference2question (ref_id);
CREATE INDEX idx_tbl_r2q_qtn_id             ON nightsquirrel.tbl_r_reference2question (qtn_id);
CREATE INDEX idx_tbl_r2a_ref_id             ON nightsquirrel.tbl_r_reference2answer   (ref_id);
CREATE INDEX idx_tbl_r2a_ans_id             ON nightsquirrel.tbl_r_reference2answer   (ans_id);

-- =============================================================================
-- TRIGGERS (updated_at — same pattern as existing tables)
-- =============================================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_person_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.per_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_publisher_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.pub_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_book_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.bok_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_article_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.art_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_video_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.vid_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_weblink_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.wlk_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_reference_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.ref_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_r_person_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_person
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_person_set_updated_at();

CREATE TRIGGER trg_r_publisher_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_publisher
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_publisher_set_updated_at();

CREATE TRIGGER trg_r_book_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_book
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_book_set_updated_at();

CREATE TRIGGER trg_r_article_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_article
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_article_set_updated_at();

CREATE TRIGGER trg_r_video_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_video
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_video_set_updated_at();

CREATE TRIGGER trg_r_weblink_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_weblink
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_weblink_set_updated_at();

CREATE TRIGGER trg_r_reference_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_reference
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_reference_set_updated_at();
