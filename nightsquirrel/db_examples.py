from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional
from datetime import datetime, timezone
import json
import json as _json


def db_list_examples(lang: str = None, qtp_id: int = None,
                     published_only: bool = False,
                     grade: str = None) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    conditions, params = [], []
    if lang:
        conditions.append("e.ex_lang = %s")
        params.append(lang)
    if qtp_id:
        conditions.append("e.qtp_id = %s")
        params.append(qtp_id)
    if published_only:
        conditions.append("e.ex_published = true")
    if grade:
        conditions.append("e.ex_grade = %s")
        params.append(grade)
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    cur.execute(f"""
        SELECT e.*, qt.qtp_name_ita, qt.qtp_name_eng
          FROM nightsquirrel.tbl_q_example e
          JOIN nightsquirrel.tbl_q_question_type qt ON qt.qtp_id = e.qtp_id
         {where}
         ORDER BY e.qtp_id, e.ex_lang, e.ex_seqno, e.ex_id
    """, params)
    return cur.fetchall()


def db_get_example(ex_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT e.*, qt.qtp_name_ita, qt.qtp_name_eng
          FROM nightsquirrel.tbl_q_example e
          JOIN nightsquirrel.tbl_q_question_type qt ON qt.qtp_id = e.qtp_id
         WHERE e.ex_id = %s
    """, (ex_id,))
    return cur.fetchone()


def db_create_example(qtp_id: int, lang: str, title: str,
                      subject: str, grade: str,
                      q_delta: dict, a_delta: dict,
                      seqno: int, published: bool) -> int:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO nightsquirrel.tbl_q_example
            (qtp_id, ex_lang, ex_title, ex_subject, ex_grade,
             ex_q_delta, ex_a_delta, ex_seqno, ex_published)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING ex_id
    """, (qtp_id, lang, title, subject or None, grade or None,
          json.dumps(q_delta), json.dumps(a_delta), seqno, published))
    ex_id = cur.fetchone()[0]
    db.commit()
    return ex_id


def db_update_example(ex_id: int, qtp_id: int, lang: str, title: str,
                      subject: str, grade: str,
                      q_delta: dict, a_delta: dict,
                      seqno: int, published: bool) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE nightsquirrel.tbl_q_example SET
            qtp_id = %s, ex_lang = %s, ex_title = %s,
            ex_subject = %s, ex_grade = %s,
            ex_q_delta = %s, ex_a_delta = %s,
            ex_seqno = %s, ex_published = %s,
            ex_updated_at = now()
         WHERE ex_id = %s
    """, (qtp_id, lang, title, subject or None, grade or None,
          json.dumps(q_delta), json.dumps(a_delta), seqno, published, ex_id))
    db.commit()


def db_delete_example(ex_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM nightsquirrel.tbl_q_example WHERE ex_id = %s",
                (ex_id,))
    db.commit()


def db_generate_examples_seed() -> str:
    db  = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    def sql_val(v):
        if v is None:               return 'NULL'
        if isinstance(v, bool):     return 'true' if v else 'false'
        if isinstance(v, int):      return str(v)
        if isinstance(v, float):    return str(v)
        if isinstance(v, datetime): return "'" + v.isoformat() + "'"
        if isinstance(v, dict):     return "'" + _json.dumps(v).replace("'", "''") + "'"
        return "'" + str(v).replace("'", "''") + "'"

    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lines = [
        f'-- {"=" * 60}',
        f'-- NightSquirrel — Examples seed',
        f'-- Generated : {generated}',
        f'-- {"=" * 60}',
        '',
        'DELETE FROM nightsquirrel.tbl_q_example;',
        '',
    ]

    cur.execute("SELECT * FROM nightsquirrel.tbl_q_example ORDER BY ex_id")
    rows = cur.fetchall()
    if rows:
        cols     = list(rows[0].keys())
        cols_sql = ', '.join(cols)
        for row in rows:
            vals = ', '.join(sql_val(row[c]) for c in cols)
            lines.append(
                f'INSERT INTO nightsquirrel.tbl_q_example ({cols_sql})'
                f' OVERRIDING SYSTEM VALUE VALUES ({vals});'
            )
        lines.append(
            "SELECT setval(pg_get_serial_sequence("
            "'nightsquirrel.tbl_q_example', 'ex_id'), "
            "COALESCE((SELECT MAX(ex_id) FROM nightsquirrel.tbl_q_example), 0));"
        )
    else:
        lines.append('-- (no examples)')

    return '\n'.join(lines) + '\n'
