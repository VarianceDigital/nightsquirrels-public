# nightsquirrel/db_tags.py
from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional


# =============================================================================
# TAG CRUD (admin only)
# =============================================================================

def db_list_tags(q: str = None) -> list:
    """Return all tags, optionally filtered by a name search string.

    Results are ordered alphabetically by tag_name_eng.
    Includes usage counts (questions + references) for the admin list view.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    if q:
        cur.execute("""
            SELECT t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type, t.tag_icon,
                   t.tag_created_at, t.tag_updated_at,
                   COUNT(DISTINCT j1.qtn_id) AS usage_questions,
                   COUNT(DISTINCT j2.ref_id) AS usage_references
              FROM nightsquirrel.tbl_t_tag t
              LEFT JOIN nightsquirrel.tbl_t_tag2question  j1 ON j1.tag_id = t.tag_id
              LEFT JOIN nightsquirrel.tbl_t_tag2reference j2 ON j2.tag_id = t.tag_id
             WHERE t.tag_name_ita ILIKE %s
                OR t.tag_name_eng ILIKE %s
             GROUP BY t.tag_id
             ORDER BY t.tag_name_eng
        """, (f'%{q}%', f'%{q}%'))
    else:
        cur.execute("""
            SELECT t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type, t.tag_icon,
                   t.tag_created_at, t.tag_updated_at,
                   COUNT(DISTINCT j1.qtn_id) AS usage_questions,
                   COUNT(DISTINCT j2.ref_id) AS usage_references
              FROM nightsquirrel.tbl_t_tag t
              LEFT JOIN nightsquirrel.tbl_t_tag2question  j1 ON j1.tag_id = t.tag_id
              LEFT JOIN nightsquirrel.tbl_t_tag2reference j2 ON j2.tag_id = t.tag_id
             GROUP BY t.tag_id
             ORDER BY t.tag_name_eng
        """)
    return cur.fetchall()


def db_get_tag(tag_id: int) -> Optional[dict]:
    """Return a single tag row by primary key."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT tag_id, tag_name_ita, tag_name_eng, tag_type, tag_icon,
               tag_created_at, tag_updated_at
          FROM nightsquirrel.tbl_t_tag
         WHERE tag_id = %s
    """, (tag_id,))
    return cur.fetchone()


def db_create_tag(name_ita: str, name_eng: str,
                  tag_type: str = None, tag_icon: str = None) -> int:
    """Insert a new tag and return its tag_id.

    Raises psycopg2.errors.UniqueViolation if either name already exists.
    """
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_t_tag
                   (tag_name_ita, tag_name_eng, tag_type, tag_icon)
            VALUES (%s, %s, %s, %s)
            RETURNING tag_id
        """, (name_ita, name_eng, tag_type or None, tag_icon or None))
        tag_id = cur.fetchone()[0]
        db.commit()
        return tag_id
    except Exception:
        db.rollback()
        raise


def db_update_tag(tag_id: int, name_ita: str, name_eng: str,
                  tag_type: str = None, tag_icon: str = None) -> bool:
    """Update an existing tag. Returns True if the row was found and updated."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_t_tag
               SET tag_name_ita = %s,
                   tag_name_eng = %s,
                   tag_type     = %s,
                   tag_icon     = %s
             WHERE tag_id = %s
        """, (name_ita, name_eng, tag_type or None, tag_icon or None, tag_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_question_for_tags(qtn_id: int, usr_id: int = None) -> Optional[dict]:
    """Return minimal question info for tag access.

    If usr_id is given, only returns a row if the user owns the question
    OR is assigned as tutor to its ticket. Pass usr_id=None for admin.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    if usr_id is None:
        cur.execute("""
            SELECT q.qtn_id, q.qtn_title, q.qtn_is_valid
              FROM nightsquirrel.tbl_q_question q
             WHERE q.qtn_id = %s
        """, (qtn_id,))
    else:
        cur.execute("""
            SELECT q.qtn_id, q.qtn_title, q.qtn_is_valid
              FROM nightsquirrel.tbl_q_question q
              LEFT JOIN nightsquirrel.tbl_t_ticket t ON t.qtn_id = q.qtn_id
             WHERE q.qtn_id = %s
               AND (q.usr_id = %s OR t.tutor_usr_id = %s)
        """, (qtn_id, usr_id, usr_id))
    return cur.fetchone()


def db_reference_for_tags(ref_id: int, usr_id: int = None) -> Optional[dict]:
    """Return minimal reference info for tag access.

    If usr_id is given, only returns if user owns the reference.
    Pass usr_id=None for admin.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    _q = """
        SELECT r.ref_id,
               COALESCE(b.bok_title, a.art_title, v.vid_title, w.wlk_title) AS ref_title
          FROM nightsquirrel.tbl_r_reference r
          LEFT JOIN nightsquirrel.tbl_r_book    b ON b.bok_id = r.ref_bok_id
          LEFT JOIN nightsquirrel.tbl_r_article a ON a.art_id = r.ref_art_id
          LEFT JOIN nightsquirrel.tbl_r_video   v ON v.vid_id = r.ref_vid_id
          LEFT JOIN nightsquirrel.tbl_r_weblink w ON w.wlk_id = r.ref_wlk_id
    """
    if usr_id is None:
        cur.execute(_q + " WHERE r.ref_id = %s", (ref_id,))
    else:
        cur.execute(_q + " WHERE r.ref_id = %s AND r.usr_id = %s", (ref_id, usr_id))
    return cur.fetchone()


def db_delete_tag(tag_id: int) -> bool:
    """Delete a tag. Junction rows are removed automatically via CASCADE."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_t_tag
             WHERE tag_id = %s
        """, (tag_id,))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# =============================================================================
# JUNCTION: tag ↔ question
# =============================================================================

def db_list_tags_for_question(qtn_id: int) -> list:
    """Return all tags attached to a question, ordered by seqno then name."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type, t.tag_icon,
               j.t2q_seqno
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_t_tag2question j ON j.tag_id = t.tag_id
         WHERE j.qtn_id = %s
         ORDER BY j.t2q_seqno, t.tag_name_eng
    """, (qtn_id,))
    return cur.fetchall()


def db_attach_tag_to_question(tag_id: int, qtn_id: int, seqno: int = 1) -> bool:
    """Attach a tag to a question. Silently ignored if already attached."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_t_tag2question (tag_id, qtn_id, t2q_seqno)
            VALUES (%s, %s, %s)
            ON CONFLICT (tag_id, qtn_id) DO NOTHING
        """, (tag_id, qtn_id, seqno))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def db_detach_tag_from_question(tag_id: int, qtn_id: int) -> bool:
    """Detach a tag from a question. Returns True if a row was removed."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_t_tag2question
             WHERE tag_id = %s AND qtn_id = %s
        """, (tag_id, qtn_id))
        ok = cur.rowcount > 0
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# =============================================================================
# JUNCTION: tag ↔ reference
# =============================================================================

def db_list_tags_for_reference(ref_id: int) -> list:
    """Return all tags attached to a reference, ordered by seqno then name."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type, t.tag_icon,
               j.t2r_seqno
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_t_tag2reference j ON j.tag_id = t.tag_id
         WHERE j.ref_id = %s
         ORDER BY j.t2r_seqno, t.tag_name_eng
    """, (ref_id,))
    return cur.fetchall()


def db_attach_tag_to_reference(tag_id: int, ref_id: int, seqno: int = 1) -> bool:
    """Attach a tag to a reference. Silently ignored if already attached."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_t_tag2reference (tag_id, ref_id, t2r_seqno)
            VALUES (%s, %s, %s)
            ON CONFLICT (tag_id, ref_id) DO NOTHING
        """, (tag_id, ref_id, seqno))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def db_detach_tag_from_reference(tag_id: int, ref_id: int) -> bool:
    """Detach a tag from a reference. Returns True if a row was removed."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_t_tag2reference
             WHERE tag_id = %s AND ref_id = %s
        """, (tag_id, ref_id))
        ok = cur.rowcount > 0
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# =============================================================================
# BATCH helpers (for list pages)
# =============================================================================

def db_tags_for_refs_batch(ref_ids: list) -> dict:
    """Return {ref_id: [tag_rows]} for a list of ref_ids. Empty list → {}."""
    if not ref_ids:
        return {}
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT j.ref_id, t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_t_tag2reference j ON j.tag_id = t.tag_id
         WHERE j.ref_id = ANY(%s)
         ORDER BY j.ref_id, j.t2r_seqno, t.tag_name_eng
    """, (ref_ids,))
    result = {}
    for row in cur.fetchall():
        result.setdefault(row['ref_id'], []).append(row)
    return result


def db_list_tags_for_library() -> list:
    """Return all tags attached to at least one library reference, with ref_count.

    Used to build the tag cloud on the library page.
    Ordered by ref_count DESC, then alphabetically.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type,
               COUNT(DISTINCT j.ref_id) AS ref_count
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_t_tag2reference j ON j.tag_id = t.tag_id
          JOIN nightsquirrel.tbl_r_reference r ON r.ref_id = j.ref_id
         WHERE r.ref_is_library = TRUE
         GROUP BY t.tag_id
         ORDER BY ref_count DESC, t.tag_name_eng
    """)
    return cur.fetchall()


def db_tags_for_questions_batch(qtn_ids: list) -> dict:
    """Return {qtn_id: [tag_rows]} for a list of qtn_ids. Empty list → {}."""
    if not qtn_ids:
        return {}
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT j.qtn_id, t.tag_id, t.tag_name_ita, t.tag_name_eng, t.tag_type
          FROM nightsquirrel.tbl_t_tag t
          JOIN nightsquirrel.tbl_t_tag2question j ON j.tag_id = t.tag_id
         WHERE j.qtn_id = ANY(%s)
         ORDER BY j.qtn_id, j.t2q_seqno, t.tag_name_eng
    """, (qtn_ids,))
    result = {}
    for row in cur.fetchall():
        result.setdefault(row['qtn_id'], []).append(row)
    return result
