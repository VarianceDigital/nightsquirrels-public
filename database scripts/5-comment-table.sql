-- 5-comment-table.sql
-- Comments on tickets (student + tutor conversation)

CREATE TABLE nightsquirrel.tbl_q_comment (
    cmt_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tkt_id          bigint NOT NULL
                      REFERENCES nightsquirrel.tbl_t_ticket(tkt_id) ON DELETE CASCADE,
    usr_id          bigint NOT NULL
                      REFERENCES nightsquirrel.tbl_u_user(usr_id) ON DELETE RESTRICT,
    ctx_id          bigint NOT NULL
                      REFERENCES nightsquirrel.tbl_q_complextext(ctx_id),
    cmt_created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tbl_q_comment_tkt_id ON nightsquirrel.tbl_q_comment(tkt_id);
