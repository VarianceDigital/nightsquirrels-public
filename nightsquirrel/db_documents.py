# nightsquirrel/db_documents.py
from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional


def db_create_document(qtn_id: int, filename: str, s3_key: str,
                       content_type: str, size_bytes: int) -> int:
    """Insert a document record. Returns doc_id."""
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_q_document
                (qtn_id, doc_filename, doc_s3_key, doc_content_type, doc_size_bytes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING doc_id
        """, (qtn_id, filename, s3_key, content_type, size_bytes))
        doc_id = cur.fetchone()['doc_id']
        db.commit()
        return doc_id
    except Exception:
        db.rollback()
        raise


def db_get_documents_for_question(qtn_id: int) -> list:
    """Return all documents for a question, ordered by creation date."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM nightsquirrel.tbl_q_document
         WHERE qtn_id = %s
         ORDER BY doc_created_at
    """, (qtn_id,))
    return cur.fetchall()


def db_get_document(doc_id: int) -> Optional[dict]:
    """Return a single document row, or None."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM nightsquirrel.tbl_q_document
         WHERE doc_id = %s
    """, (doc_id,))
    return cur.fetchone()


def db_save_extracted_delta(doc_id: int, delta_json: str) -> None:
    """Save the AI-extracted Quill delta JSON for an image document."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_q_document
               SET doc_extracted_delta = %s
             WHERE doc_id = %s
        """, (delta_json, doc_id))
        db.commit()
    except Exception:
        db.rollback()
        raise


def db_delete_document(doc_id: int) -> Optional[str]:
    """Delete a document row. Returns the S3 key for cleanup, or None if not found."""
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_q_document
             WHERE doc_id = %s
            RETURNING doc_s3_key
        """, (doc_id,))
        row = cur.fetchone()
        db.commit()
        return row['doc_s3_key'] if row else None
    except Exception:
        db.rollback()
        raise
