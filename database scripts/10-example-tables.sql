-- ─────────────────────────────────────────────────────────────────────────────
-- EXAMPLES  (admin-curated Q&A examples, one per question type per language)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_example (
    ex_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    qtp_id        bigint       NOT NULL,
    ex_lang       char(2)      NOT NULL DEFAULT 'it',
    ex_title      varchar(512) NOT NULL,
    ex_subject    varchar(256),
    ex_grade      varchar(64),
    ex_q_delta    jsonb        NOT NULL DEFAULT '{"ops":[]}',
    ex_a_delta    jsonb        NOT NULL DEFAULT '{"ops":[]}',
    ex_seqno      integer      NOT NULL DEFAULT 0,
    ex_published  boolean      NOT NULL DEFAULT false,
    ex_created_at timestamptz  NOT NULL DEFAULT now(),
    ex_updated_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_tbl_q_example_qtp
        FOREIGN KEY (qtp_id)
        REFERENCES nightsquirrel.tbl_q_question_type (qtp_id),
    CONSTRAINT chk_tbl_q_example_lang
        CHECK (ex_lang IN ('it', 'en'))
);

CREATE INDEX IF NOT EXISTS idx_tbl_q_example_qtp_lang
    ON nightsquirrel.tbl_q_example (qtp_id, ex_lang);
