-- 4-document-table.sql
-- Document attachments for questions (images, PDFs)

CREATE TABLE nightsquirrel.tbl_q_document (
    doc_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    qtn_id          bigint NOT NULL REFERENCES nightsquirrel.tbl_q_question(qtn_id) ON DELETE CASCADE,
    doc_filename    varchar(255) NOT NULL,
    doc_s3_key      varchar(512) NOT NULL UNIQUE,
    doc_content_type varchar(100) NOT NULL,
    doc_size_bytes  bigint NOT NULL,
    doc_extracted_delta text,
    doc_created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tbl_q_document_qtn_id ON nightsquirrel.tbl_q_document(qtn_id);
