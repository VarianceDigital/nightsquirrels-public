from psycopg2.extras import RealDictCursor, Json
from .db import get_db


def db_create_book_draft(isbn: str, raw_data: dict, cover_url: str | None = None) -> int:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        INSERT INTO nightsquirrel.tbl_r_book_draft (isbn, raw_data, cover_url)
        VALUES (%s, %s, %s)
        RETURNING draft_id
        """,
        (isbn, Json(raw_data), cover_url),
    )
    draft_id = cur.fetchone()['draft_id']
    db.commit()
    return draft_id


def db_list_book_drafts(processed: bool | None = None):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    if processed is None:
        cur.execute(
            "SELECT * FROM nightsquirrel.tbl_r_book_draft ORDER BY draft_created_at DESC"
        )
    else:
        cur.execute(
            "SELECT * FROM nightsquirrel.tbl_r_book_draft WHERE draft_processed = %s "
            "ORDER BY draft_created_at DESC",
            (processed,),
        )
    return cur.fetchall()


def db_get_book_draft(draft_id: int):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM nightsquirrel.tbl_r_book_draft WHERE draft_id = %s",
        (draft_id,),
    )
    return cur.fetchone()


def db_mark_draft_processed(draft_id: int, ref_id: int) -> None:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE nightsquirrel.tbl_r_book_draft
           SET draft_processed = TRUE, draft_ref_id = %s
         WHERE draft_id = %s
    """, (ref_id, draft_id))
    db.commit()


def db_mark_draft_already_present(draft_id: int) -> None:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE nightsquirrel.tbl_r_book_draft
           SET draft_processed = TRUE, draft_already_present = TRUE
         WHERE draft_id = %s
    """, (draft_id,))
    db.commit()


def db_mark_draft_error(draft_id: int, error_msg: str) -> None:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE nightsquirrel.tbl_r_book_draft
           SET draft_error = %s
         WHERE draft_id = %s
    """, (error_msg, draft_id))
    db.commit()


def db_delete_draft_by_ref_id(ref_id: int) -> None:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "DELETE FROM nightsquirrel.tbl_r_book_draft WHERE draft_ref_id = %s",
        (ref_id,))
    db.commit()


def db_delete_book_draft(draft_id: int) -> bool:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "DELETE FROM nightsquirrel.tbl_r_book_draft WHERE draft_id = %s",
        (draft_id,),
    )
    ok = cur.rowcount > 0
    db.commit()
    return ok


def db_flush_completed_drafts() -> int:
    """Delete all drafts that are no longer actionable (processed, already-present,
    or errored). Pending unprocessed drafts are left untouched.
    Returns the number of rows deleted."""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        DELETE FROM nightsquirrel.tbl_r_book_draft
         WHERE draft_processed = true
            OR draft_already_present = true
            OR draft_error IS NOT NULL
    """)
    count = cur.rowcount
    db.commit()
    return count
