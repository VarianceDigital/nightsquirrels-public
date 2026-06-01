--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA nightsquirrel;


CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_u_user (
    usr_id bigint NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 9223372036854775807 CACHE 1 ),
    usr_email character varying(255) NOT NULL UNIQUE,
    usr_key character varying(128) NOT NULL,
    usr_name character varying(100) UNIQUE,
    usr_isvalid boolean DEFAULT true NOT NULL,
    usr_confirmed boolean DEFAULT false,
    usr_timestamp timestamp with time zone  NOT NULL DEFAULT now(),
    usr_otp character varying(10),
    usr_key_temp character varying(128),
    usr_tile character varying(50),
    usr_is_student boolean NOT NULL DEFAULT true,
    usr_is_tutor boolean NOT NULL DEFAULT false,
    usr_is_admin boolean NOT NULL DEFAULT false,
    usr_is_payer boolean NOT NULL DEFAULT false,
    usr_birthday character varying(15) COLLATE pg_catalog."default",
    sct_id bigint,
    usr_school_grade integer,
    CONSTRAINT tbl_u_user_pkey PRIMARY KEY (usr_id)
);

COMMENT ON COLUMN nightsquirrel.tbl_u_user.sct_id
    IS 'School Type';


CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_question
(
    qtn_id bigint NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 9223372036854775807 CACHE 1 ),
	  usr_id bigint NOT NULL,
	  qtn_title character varying(1024) COLLATE pg_catalog."default" NOT NULL,
    sbj_id bigint,
	  qtp_id bigint,
    sct_id bigint,
    ctx_id bigint NOT NULL UNIQUE,
    qtn_notes text COLLATE pg_catalog."default",
    qtn_difficulty integer,
    qtn_grade integer,
    qtn_is_valid boolean NOT NULL DEFAULT true,
	  qtn_state integer NOT NULL DEFAULT 0,
    qtn_created_at timestamptz NOT NULL DEFAULT now(),
    qtn_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tbl_question_pkey PRIMARY KEY (qtn_id)
);

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_subject
(
    sbj_id bigint NOT NULL,
    sbj_name_ita character varying(512) NOT NULL,
    sbj_name_eng character varying(512) NOT NULL,
    sbj_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT tbl_q_subject_pkey PRIMARY KEY (sbj_id)
);

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_s_schooltype
(
    sct_id bigint NOT NULL,
    sct_name_ita character varying(512) NOT NULL,
    sct_name_eng character varying(512) NOT NULL,
    sct_years integer NOT NULL,
    sct_seqno integer NOT NULL DEFAULT 1,
    CONSTRAINT tbl_s_schooltype_pkey PRIMARY KEY (sct_id)
);

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_question_type
(
    qtp_id bigint NOT NULL,
    qtp_name_ita character varying(250) NOT NULL,
    qtp_name_eng character varying(250) NOT NULL,
    qtp_seqno integer NOT NULL,

    CONSTRAINT tbl_q_question_type_pkey PRIMARY KEY (qtp_id)
);


CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_complextext
(
    ctx_id bigint NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 9223372036854775807 CACHE 1 ),
    ctx_delta jsonb NOT NULL,
    ctx_plaintext text,
    ctx_createdwhen timestamp with time zone NOT NULL DEFAULT now(),
    ctx_modifiedwhen timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT tbl_q_complextext_pkey PRIMARY KEY (ctx_id)
);

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_t_ticket (
  tkt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  qtn_id bigint NOT NULL UNIQUE,
  tutor_usr_id bigint NULL,
  ans_id bigint UNIQUE,
  tkt_state integer NOT NULL DEFAULT 0,

  -- Quote timestamps
  tkt_quoted_at   timestamptz NULL,
  tkt_accepted_at timestamptz NULL,
  tkt_rejected_at timestamptz NULL,

  -- Quote meta
  tkt_quote_points  integer NULL,
  tkt_quote_version varchar(32) NULL,
  tkt_quote_note    text NULL,
  tkt_currency      char(3) NOT NULL DEFAULT 'EUR',

  -- Quote payload (NEW)
  tkt_quote_payload   jsonb NULL,
  tkt_quote_signature varchar(64) NULL,
  tkt_quote_input     jsonb NULL,

  -- Student selection (NEW)
  tkt_selected_option_id    varchar(64) NULL,
  tkt_selected_quote_cents  integer NULL,

  -- AI analysis
  tkt_ai_analysis jsonb NULL,
  tkt_ai_hint     text NULL,

  -- Delivery / audit
  tkt_due_at     timestamptz NULL,
  tkt_closed_at  timestamptz NULL,
  tkt_created_at timestamptz NOT NULL DEFAULT now(),
  tkt_updated_at timestamptz NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT chk_ticket_ai_analysis_is_object
    CHECK (tkt_ai_analysis IS NULL OR jsonb_typeof(tkt_ai_analysis) = 'object'),
  CONSTRAINT chk_ticket_quote_payload_is_object
    CHECK (tkt_quote_payload IS NULL OR jsonb_typeof(tkt_quote_payload) = 'object'),
  CONSTRAINT chk_ticket_quote_input_is_object
    CHECK (tkt_quote_input IS NULL OR jsonb_typeof(tkt_quote_input) = 'object'),
  CONSTRAINT chk_ticket_selected_quote_nonneg
    CHECK (tkt_selected_quote_cents IS NULL OR tkt_selected_quote_cents >= 0)
);

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_q_answer (
  ans_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  qtn_id bigint NOT NULL UNIQUE,          -- which question this answers
  tkt_id bigint NOT NULL UNIQUE,          -- which ticket owns the answer
  ctx_id bigint NOT NULL UNIQUE,          -- Quill delta stored in tbl_q_complextext
  ans_state integer NOT NULL DEFAULT 0,   
  ans_is_valid boolean NOT NULL DEFAULT true,
  ans_created_at timestamptz NOT NULL DEFAULT now(),
  ans_updated_at timestamptz NOT NULL DEFAULT now()
);


ALTER TABLE nightsquirrel.tbl_u_user
  ADD CONSTRAINT fk_tbl_u_user_tbl_s_schooltype
  FOREIGN KEY (sct_id)
  REFERENCES nightsquirrel.tbl_s_schooltype (sct_id);

ALTER TABLE nightsquirrel.tbl_q_question
  ADD CONSTRAINT fk_tbl_q_question_tbl_u_user
  FOREIGN KEY (usr_id)
  REFERENCES nightsquirrel.tbl_u_user (usr_id)
  ON DELETE RESTRICT;

-- Question -> Subject
ALTER TABLE nightsquirrel.tbl_q_question
  ADD CONSTRAINT fk_tbl_q_question_tbl_q_subject
  FOREIGN KEY (sbj_id)
  REFERENCES nightsquirrel.tbl_q_subject (sbj_id)
  ON DELETE SET NULL;

-- Question -> QuestionType
ALTER TABLE nightsquirrel.tbl_q_question
  ADD CONSTRAINT fk_tbl_q_question_tbl_q_question_type
  FOREIGN KEY (qtp_id)
  REFERENCES nightsquirrel.tbl_q_question_type (qtp_id)
  ON DELETE SET NULL;

-- Question -> SchoolType (if question is tagged with school type)
ALTER TABLE nightsquirrel.tbl_q_question
  ADD CONSTRAINT fk_tbl_q_question_tbl_s_schooltype
  FOREIGN KEY (sct_id)
  REFERENCES nightsquirrel.tbl_s_schooltype (sct_id)
  ON DELETE SET NULL;

-- Question -> ComplexText (the Quill delta for the question body)
ALTER TABLE nightsquirrel.tbl_q_question
  ADD CONSTRAINT fk_tbl_q_question_tbl_q_complextext
  FOREIGN KEY (ctx_id)
  REFERENCES nightsquirrel.tbl_q_complextext (ctx_id);
-- STRUCTURE AND TEXT SHOULD BE DELETED VIA CODE WHEN QUESTION OR ANSWER DISAPPEAR
  
ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT fk_tbl_t_ticket_tbl_q_question
  FOREIGN KEY (qtn_id)
  REFERENCES nightsquirrel.tbl_q_question(qtn_id)
  ON DELETE CASCADE;

ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT fk_tbl_t_ticket_tutor
  FOREIGN KEY (tutor_usr_id)
  REFERENCES nightsquirrel.tbl_u_user(usr_id)
  ON DELETE SET NULL;

ALTER TABLE nightsquirrel.tbl_q_answer
  ADD CONSTRAINT fk_tbl_q_answer_tbl_q_question
  FOREIGN KEY (qtn_id)
  REFERENCES nightsquirrel.tbl_q_question (qtn_id)
  ON DELETE CASCADE;

ALTER TABLE nightsquirrel.tbl_q_answer
  ADD CONSTRAINT fk_tbl_q_answer_tbl_q_complextext
  FOREIGN KEY (ctx_id)
  REFERENCES nightsquirrel.tbl_q_complextext (ctx_id);

ALTER TABLE nightsquirrel.tbl_q_answer
  ADD CONSTRAINT fk_tbl_q_answer_tbl_t_ticket
  FOREIGN KEY (tkt_id)
  REFERENCES nightsquirrel.tbl_t_ticket (tkt_id)
  ON DELETE CASCADE;
  
ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT fk_tbl_t_ticket_tbl_q_answer
  FOREIGN KEY (ans_id)
  REFERENCES nightsquirrel.tbl_q_answer (ans_id)
  ON DELETE SET NULL;

-- DOUBLE LINK answwer <-> ticket
ALTER TABLE nightsquirrel.tbl_q_answer
  ADD CONSTRAINT uq_tbl_q_answer_ans_tkt UNIQUE (ans_id, tkt_id);

ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT fk_tbl_t_ticket_ans_belongs_to_ticket
  FOREIGN KEY (ans_id, tkt_id)
  REFERENCES nightsquirrel.tbl_q_answer (ans_id, tkt_id);

ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT chk_ticket_accept_reject_exclusive
  CHECK (
    NOT (tkt_accepted_at IS NOT NULL AND tkt_rejected_at IS NOT NULL)
  );

ALTER TABLE nightsquirrel.tbl_t_ticket
  ADD CONSTRAINT chk_ticket_quoted_fields_coherent
  CHECK (
    (tkt_quoted_at IS NULL AND tkt_quote_points IS NULL AND tkt_quote_version IS NULL)
    OR
    (tkt_quoted_at IS NOT NULL AND tkt_quote_version IS NOT NULL)
  );

CREATE INDEX idx_tbl_q_question_usr_id ON nightsquirrel.tbl_q_question (usr_id);
CREATE INDEX idx_tbl_q_question_sbj_id ON nightsquirrel.tbl_q_question (sbj_id);
CREATE INDEX idx_tbl_q_question_qtp_id ON nightsquirrel.tbl_q_question (qtp_id);
CREATE INDEX idx_tbl_q_question_sct_id ON nightsquirrel.tbl_q_question (sct_id);
CREATE INDEX idx_tbl_u_user_sct_id ON nightsquirrel.tbl_u_user (sct_id);
CREATE INDEX idx_tbl_t_ticket_tutor_usr_id ON nightsquirrel.tbl_t_ticket (tutor_usr_id);
CREATE INDEX idx_tbl_t_ticket_state ON nightsquirrel.tbl_t_ticket (tkt_state);
CREATE INDEX idx_tbl_t_ticket_due_at ON nightsquirrel.tbl_t_ticket (tkt_due_at);
CREATE INDEX idx_tbl_t_ticket_tutor_state ON nightsquirrel.tbl_t_ticket (tutor_usr_id, tkt_state);
CREATE INDEX idx_tbl_q_answer_state ON nightsquirrel.tbl_q_answer (ans_state);
CREATE INDEX idx_tbl_q_subject_seqno ON nightsquirrel.tbl_q_subject (sbj_seqno);
CREATE INDEX idx_tbl_s_schooltype_seqno ON nightsquirrel.tbl_s_schooltype (sct_seqno);
CREATE INDEX idx_tbl_q_question_type_seqno ON nightsquirrel.tbl_q_question_type (qtp_seqno);
CREATE INDEX idx_tbl_q_question_state ON nightsquirrel.tbl_q_question (qtn_state);
CREATE INDEX idx_tbl_q_question_valid ON nightsquirrel.tbl_q_question (qtn_is_valid);
CREATE INDEX idx_tbl_q_question_created_at ON nightsquirrel.tbl_q_question (qtn_created_at DESC);
CREATE INDEX idx_tbl_q_question_usr_created_at ON nightsquirrel.tbl_q_question (usr_id, qtn_created_at DESC);
CREATE INDEX idx_ticket_state ON nightsquirrel.tbl_t_ticket (tkt_state);
CREATE INDEX idx_ticket_quoted_at ON nightsquirrel.tbl_t_ticket (tkt_quoted_at);
CREATE INDEX idx_ticket_accepted_at ON nightsquirrel.tbl_t_ticket (tkt_accepted_at);
CREATE INDEX idx_ticket_quote_signature ON nightsquirrel.tbl_t_ticket (tkt_quote_signature);
CREATE INDEX idx_ticket_selected_option ON nightsquirrel.tbl_t_ticket (tkt_selected_option_id);

--TRIGGERS!
CREATE OR REPLACE FUNCTION nightsquirrel.fn_ticket_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.tkt_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_answer_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.ans_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_complextext_set_modifiedwhen()
RETURNS trigger AS $$
BEGIN
  NEW.ctx_modifiedwhen := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nightsquirrel.fn_question_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.qtn_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_t_ticket
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_ticket_set_updated_at();

CREATE TRIGGER trg_answer_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_q_answer
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_answer_set_updated_at();

CREATE TRIGGER trg_complextext_set_modifiedwhen
BEFORE UPDATE ON nightsquirrel.tbl_q_complextext
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_complextext_set_modifiedwhen();

CREATE TRIGGER trg_question_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_q_question
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_question_set_updated_at();


INSERT INTO nightsquirrel.tbl_q_subject VALUES (0, 'Altro', 'Other', 9);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (1, 'Matematica', 'Maths', 1);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (2, 'Italiano/Letteratura', 'Italian Literature', 2);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (3, 'Inglese', 'English', 3);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (4, 'Fisica', 'Physics', 4);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (5, 'Filosofia', 'Philosophy', 5);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (6, 'Informatica', 'Computer Science', 6);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (7, 'Musica', 'Music', 7);
INSERT INTO nightsquirrel.tbl_q_subject VALUES (8, 'Intelligenza artificiale', 'Artificial Intelligence', 8);

INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (1, 'Scuola Primaria (Elementari)', 'Scuola Primaria (Elementari)', 5, 1);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (2, 'Scuola Media', 'Scuola Media', 3, 2);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (3, 'Liceo Artistico', 'Liceo Artistico', 5, 3);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (4, 'Liceo Classico', 'Liceo Classico', 5, 4);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (5, 'Liceo Linguistico', 'Liceo Linguistico', 5, 5);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (6, 'Liceo Musicale', 'Liceo Musicale', 5, 6);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (7, 'Liceo Scienze Umane', 'Liceo Scienze Umane', 5, 7);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (8, 'Liceo Scientifico', 'Liceo Scientifico', 5, 8);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (9, 'Istituto Professionale', 'Istituto Professionale', 5, 9);
INSERT INTO nightsquirrel.tbl_s_schooltype VALUES (10, 'Università', 'Università', 3, 10);

INSERT INTO nightsquirrel.tbl_q_question_type VALUES
    (1, 'Esercizio singolo',             'Single exercise',         1),
    (2, 'Serie di esercizi',             'Exercise set',            2),
    (3, 'Spiegazione di concetto',       'Explain a concept',       3),
    (4, 'Passaggi / dimostrazione',      'Show the steps / prove',  4),
    (5, 'Riassunto / schema / mappa',    'Summary / schema / mind map', 5),
    (6, 'Timeline (Sequenza temporale)', 'Timeline',                6),
    (7, 'Tema / elaborato scritto',      'Essay / written work',    7),
    (8, 'Progetto / presentazione',      'Project / presentation',  8);

-- DEFAULT USERS
-- ADMIN USER ->>> CRUCIAL!
INSERT INTO nightsquirrel.tbl_u_user (                                                                                                           
    usr_id, usr_email, usr_key, usr_name,
    usr_isvalid, usr_confirmed, usr_tile,
    usr_is_student, usr_is_tutor, usr_is_admin, usr_is_payer,                                                                                           
    sct_id, usr_school_grade)
OVERRIDING SYSTEM VALUE                                                                                                                                 
VALUES (1, 'variance.milano@gmail.com', 
        'sha256$lxMnvIx0yDBYjPDy$e17cf3a475356d414e28d1a69a75b195b4026c6fc406a832517ee3dc40bc689d', 
        'AdminTutor', true, true, 'tile6.svg', false, true, true, false, NULL, NULL);

INSERT INTO nightsquirrel.tbl_u_user (                                                                          
    usr_id, usr_email, usr_key, usr_name,                                                                       
    usr_isvalid, usr_confirmed, usr_tile,
    usr_is_student, usr_is_tutor, usr_is_admin, usr_is_payer,
    sct_id, usr_school_grade)                                                                                   
OVERRIDING SYSTEM VALUE
VALUES (2, 'rinaldo.nani@gmail.com',                                                                          
        'sha256$lxMnvIx0yDBYjPDy$e17cf3a475356d414e28d1a69a75b195b4026c6fc406a832517ee3dc40bc689d',             
        'RinaldoTutor', true, true, 'tile6.svg', false, true, false, false, NULL, NULL);                               
                                                                                                                
INSERT INTO nightsquirrel.tbl_u_user (                                                                          
    usr_id, usr_email, usr_key, usr_name,
    usr_isvalid, usr_confirmed, usr_tile,                                                                       
    usr_is_student, usr_is_tutor, usr_is_admin, usr_is_payer,
    sct_id, usr_school_grade)                                                                                   
OVERRIDING SYSTEM VALUE
VALUES (3, 'beethovenreview@gmail.com',                                                                        
        'sha256$lxMnvIx0yDBYjPDy$e17cf3a475356d414e28d1a69a75b195b4026c6fc406a832517ee3dc40bc689d',
        'StudentBeeth', true, true, 'tile6.svg', true, false, false, false, NULL, NULL);  

SELECT setval(
      pg_get_serial_sequence('nightsquirrel.tbl_u_user', 'usr_id'),
      (SELECT MAX(usr_id) FROM nightsquirrel.tbl_u_user)
  );       