-- ============================================================
-- NightSquirrel — Examples seed
-- Generated : 2026-05-05 22:33 UTC
-- ============================================================

DELETE FROM nightsquirrel.tbl_q_example;

INSERT INTO nightsquirrel.tbl_q_example (ex_id, qtp_id, ex_lang, ex_title, ex_subject, ex_grade, ex_q_delta, ex_a_delta, ex_seqno, ex_published, ex_created_at, ex_updated_at) OVERRIDING SYSTEM VALUE VALUES (1, 1, 'it', 'Prova HS', NULL, '3', '{"ops": [{"insert": "Domanda HS\n"}]}', '{"ops": [{"insert": "Risposta HS\n"}]}', 0, true, '2026-04-28T12:33:44.278709+00:00', '2026-04-28T12:34:08.944642+00:00');
SELECT setval(pg_get_serial_sequence('nightsquirrel.tbl_q_example', 'ex_id'), COALESCE((SELECT MAX(ex_id) FROM nightsquirrel.tbl_q_example), 0));
