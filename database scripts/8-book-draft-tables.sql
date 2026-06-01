-- 8-book-draft-tables.sql
-- Book draft import pipeline: draft staging table for ISBN scan import

-- ─────────────────────────────────────────────────────────────────────────────
-- BOOK DRAFT (staging table for ISBN scan import pipeline)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_r_book_draft
(
    draft_id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn                   character varying(20)  NOT NULL,
    raw_data               jsonb                  NOT NULL,           -- full Open Library / Google Books response
    cover_url              character varying(500),                    -- cover image URL found at scan time, if any
    draft_processed        boolean NOT NULL DEFAULT false,            -- true after processing attempt
    draft_already_present  boolean NOT NULL DEFAULT false,            -- true if ISBN already in tbl_r_book
    draft_ref_id           bigint,                                    -- FK → created tbl_r_reference, if any
    draft_error            text,                                      -- error message if processing failed
    draft_created_at       timestamptz NOT NULL DEFAULT now(),
    draft_updated_at       timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- FOREIGN KEY
-- =============================================================================

ALTER TABLE nightsquirrel.tbl_r_book_draft ADD CONSTRAINT fk_tbl_r_book_draft_ref
    FOREIGN KEY (draft_ref_id) REFERENCES nightsquirrel.tbl_r_reference (ref_id)
    ON DELETE SET NULL;

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_tbl_r_book_draft_isbn        ON nightsquirrel.tbl_r_book_draft (isbn);
CREATE INDEX idx_tbl_r_book_draft_processed   ON nightsquirrel.tbl_r_book_draft (draft_processed);
CREATE INDEX idx_tbl_r_reference_needs_review ON nightsquirrel.tbl_r_reference  (ref_needs_review)
    WHERE ref_needs_review = true;

-- =============================================================================
-- TRIGGER (updated_at)
-- =============================================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_r_book_draft_set_updated_at()
RETURNS trigger AS $$ BEGIN NEW.draft_updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_r_book_draft_set_updated_at
    BEFORE UPDATE ON nightsquirrel.tbl_r_book_draft
    FOR EACH ROW EXECUTE FUNCTION nightsquirrel.fn_r_book_draft_set_updated_at();
