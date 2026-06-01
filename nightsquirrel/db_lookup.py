from psycopg2.extras import RealDictCursor
from .db import get_db

def db_get_subjects():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT sbj_id, sbj_name_ita, sbj_name_eng, sbj_seqno
        FROM nightsquirrel.tbl_q_subject
        ORDER BY sbj_seqno, sbj_id
    """)
    return cur.fetchall()

def db_get_questiontypes():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT qtp_id, qtp_name_ita, qtp_name_eng, qtp_seqno
        FROM nightsquirrel.tbl_q_question_type
        ORDER BY qtp_seqno, qtp_id
    """)
    return cur.fetchall()

def db_get_schooltypes():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT sct_id, sct_name_ita, sct_name_eng, sct_years, sct_seqno
        FROM nightsquirrel.tbl_s_schooltype
        ORDER BY sct_seqno, sct_id
    """)
    return cur.fetchall()
