from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional
import json
from .db_references import _REF_LIST_QUERY


def db_list_ideas(lang: str = None, published_only: bool = False,
                  usr_id: int = None) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    conditions, params = [], []
    if lang:
        conditions.append("i.idea_lang = %s")
        params.append(lang)
    if published_only:
        conditions.append("i.idea_is_published = true")
    if usr_id:
        conditions.append("i.usr_id = %s")
        params.append(usr_id)
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    cur.execute(f"""
        SELECT i.*,
               u.usr_name
          FROM nightsquirrel.tbl_i_idea i
          JOIN nightsquirrel.tbl_u_user u ON u.usr_id = i.usr_id
         {where}
         ORDER BY i.idea_lang, i.idea_title
    """, params)
    return cur.fetchall()


def db_get_idea(idea_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT i.*,
               u.usr_name
          FROM nightsquirrel.tbl_i_idea i
          JOIN nightsquirrel.tbl_u_user u ON u.usr_id = i.usr_id
         WHERE i.idea_id = %s
    """, (idea_id,))
    return cur.fetchone()


def db_create_idea(title: str, lang: str, usr_id: int,
                   subtitle: str = None, published: bool = False) -> int:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO nightsquirrel.tbl_i_idea
            (idea_title, idea_subtitle, idea_lang, usr_id, idea_is_published)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING idea_id
    """, (title, subtitle or None, lang, usr_id, published))
    idea_id = cur.fetchone()[0]
    db.commit()
    return idea_id


def db_update_idea(idea_id: int, title: str, lang: str,
                   subtitle: str = None, published: bool = False) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE nightsquirrel.tbl_i_idea SET
            idea_title        = %s,
            idea_subtitle     = %s,
            idea_lang         = %s,
            idea_is_published = %s,
            idea_updated_at   = now()
         WHERE idea_id = %s
    """, (title, subtitle or None, lang, published, idea_id))
    db.commit()


def db_update_idea_body(idea_id: int, body_delta: dict) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE nightsquirrel.tbl_i_idea SET
            idea_body_delta = %s,
            idea_updated_at = now()
         WHERE idea_id = %s
    """, (json.dumps(body_delta), idea_id))
    db.commit()


def db_delete_idea(idea_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM nightsquirrel.tbl_i_idea WHERE idea_id = %s",
                (idea_id,))
    db.commit()


# ── Tag junctions ─────────────────────────────────────────────────────────────

def db_list_tags_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.*
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_i_idea2tag j ON j.tag_id = t.tag_id
         WHERE j.idea_id = %s
         ORDER BY t.tag_name_ita
    """, (idea_id,))
    return cur.fetchall()


def db_list_tags_available_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.*
          FROM nightsquirrel.tbl_t_tag t
         WHERE t.tag_id NOT IN (
               SELECT tag_id FROM nightsquirrel.tbl_i_idea2tag
                WHERE idea_id = %s)
         ORDER BY t.tag_name_ita
    """, (idea_id,))
    return cur.fetchall()


def db_attach_tag_to_idea(idea_id: int, tag_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO nightsquirrel.tbl_i_idea2tag (idea_id, tag_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (idea_id, tag_id))
    db.commit()


def db_detach_tag_from_idea(idea_id: int, tag_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        DELETE FROM nightsquirrel.tbl_i_idea2tag
         WHERE idea_id = %s AND tag_id = %s
    """, (idea_id, tag_id))
    db.commit()


# ── Reference junctions ───────────────────────────────────────────────────────

def db_list_refs_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"""
        {_REF_LIST_QUERY}
          JOIN nightsquirrel.tbl_i_idea2reference j ON j.ref_id = r.ref_id
         WHERE j.idea_id = %s
         ORDER BY ref_title
    """, (idea_id,))
    return cur.fetchall()


def db_list_refs_available_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"""
        {_REF_LIST_QUERY}
         WHERE r.ref_is_library = true
           AND r.ref_id NOT IN (
               SELECT ref_id FROM nightsquirrel.tbl_i_idea2reference
                WHERE idea_id = %s)
         ORDER BY ref_title
    """, (idea_id,))
    return cur.fetchall()


def db_attach_ref_to_idea(idea_id: int, ref_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO nightsquirrel.tbl_i_idea2reference (idea_id, ref_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (idea_id, ref_id))
    db.commit()


def db_detach_ref_from_idea(idea_id: int, ref_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        DELETE FROM nightsquirrel.tbl_i_idea2reference
         WHERE idea_id = %s AND ref_id = %s
    """, (idea_id, ref_id))
    db.commit()


# ── Answer junctions ──────────────────────────────────────────────────────────

def db_list_answers_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.ans_id, q.qtn_id, q.qtn_title
          FROM nightsquirrel.tbl_q_answer a
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = a.qtn_id
          JOIN nightsquirrel.tbl_i_idea2answer j ON j.ans_id = a.ans_id
         WHERE j.idea_id = %s
         ORDER BY q.qtn_title
    """, (idea_id,))
    return cur.fetchall()


def db_list_answers_available_for_idea(idea_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.ans_id, q.qtn_id, q.qtn_title
          FROM nightsquirrel.tbl_q_answer a
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = a.qtn_id
         WHERE a.ans_id NOT IN (
               SELECT ans_id FROM nightsquirrel.tbl_i_idea2answer
                WHERE idea_id = %s)
         ORDER BY q.qtn_title
    """, (idea_id,))
    return cur.fetchall()


def db_attach_answer_to_idea(idea_id: int, ans_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO nightsquirrel.tbl_i_idea2answer (idea_id, ans_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (idea_id, ans_id))
    db.commit()


def db_detach_answer_from_idea(idea_id: int, ans_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        DELETE FROM nightsquirrel.tbl_i_idea2answer
         WHERE idea_id = %s AND ans_id = %s
    """, (idea_id, ans_id))
    db.commit()
