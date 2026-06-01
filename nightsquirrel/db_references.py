# nightsquirrel/db_references.py
# DB layer for the References module:
# persons, publishers, books, articles, videos, weblinks,
# reference images, references, and junction tables.

from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional


# =============================================================================
# PERSONS
# =============================================================================

def db_list_persons(q: str = None, needs_enrich: bool = False) -> list:
    """List persons, optionally filtered by name search or missing captions."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if q:
        pattern = f'%{q.lower()}%'
        conditions.append(
            "(LOWER(COALESCE(per_firstname,'') || ' ' || COALESCE(per_familyname,'')) LIKE %s"
            " OR LOWER(COALESCE(per_strings,'')) LIKE %s)"
        )
        params += [pattern, pattern]
    if needs_enrich:
        conditions.append(
            "(per_caption_ita IS NULL OR per_caption_eng IS NULL)"
        )
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    cur.execute(f"""
        SELECT * FROM nightsquirrel.tbl_r_person
         {where}
         ORDER BY per_familyname, per_firstname
    """, params)
    return cur.fetchall()


def db_get_person(per_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_person WHERE per_id = %s", (per_id,))
    return cur.fetchone()


def db_create_person(firstname: str, familyname: str,
                     caption_ita: str = None, caption_eng: str = None,
                     strings: str = None, won_nobel: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_person
                (per_firstname, per_familyname, per_caption_ita, per_caption_eng,
                 per_strings, per_won_nobel)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING per_id
        """, (firstname or None, familyname or None,
              caption_ita or None, caption_eng or None,
              strings or None, won_nobel or None))
        per_id = cur.fetchone()['per_id']
        db.commit()
        return per_id
    except Exception:
        db.rollback()
        raise


def db_update_person(per_id: int, firstname: str, familyname: str,
                     caption_ita: str = None, caption_eng: str = None,
                     strings: str = None, won_nobel: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_person
               SET per_firstname = %s, per_familyname = %s,
                   per_caption_ita = %s, per_caption_eng = %s,
                   per_strings = %s, per_won_nobel = %s
             WHERE per_id = %s
        """, (firstname or None, familyname or None,
              caption_ita or None, caption_eng or None,
              strings or None, won_nobel or None, per_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_person(per_id: int) -> bool:
    """Delete a person. Raises if still referenced by books/articles (FK RESTRICT)."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_person WHERE per_id = %s", (per_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_find_persons_by_familyname(familyname: str) -> list:
    """Fuzzy candidates for AI matching: persons whose familyname contains the string."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT per_id, per_firstname, per_familyname
          FROM nightsquirrel.tbl_r_person
         WHERE LOWER(per_familyname) LIKE LOWER(%s)
         ORDER BY per_familyname, per_firstname
         LIMIT 20
    """, (f'%{familyname}%',))
    return cur.fetchall()


def db_find_person_by_name(firstname: str, familyname: str) -> int | None:
    """Case-insensitive exact match on firstname + familyname. Returns per_id or None."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT per_id FROM nightsquirrel.tbl_r_person
         WHERE LOWER(COALESCE(per_familyname, '')) = LOWER(%s)
           AND LOWER(COALESCE(per_firstname,  '')) = LOWER(%s)
         LIMIT 1
    """, (familyname or '', firstname or ''))
    row = cur.fetchone()
    return row['per_id'] if row else None


# =============================================================================
# PUBLISHERS
# =============================================================================

def db_list_publishers(q: str = None) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    if q:
        pattern = f'%{q.lower()}%'
        cur.execute("""
            SELECT * FROM nightsquirrel.tbl_r_publisher
             WHERE LOWER(pub_name) LIKE %s OR LOWER(COALESCE(pub_othername,'')) LIKE %s
             ORDER BY pub_name
        """, (pattern, pattern))
    else:
        cur.execute("SELECT * FROM nightsquirrel.tbl_r_publisher ORDER BY pub_name")
    return cur.fetchall()


def db_get_publisher(pub_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_publisher WHERE pub_id = %s", (pub_id,))
    return cur.fetchone()


def db_create_publisher(name: str, othername: str = None,
                        location: str = None, description: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_publisher
                (pub_name, pub_othername, pub_location, pub_description)
            VALUES (%s, %s, %s, %s)
            RETURNING pub_id
        """, (name, othername or None, location or None, description or None))
        pub_id = cur.fetchone()['pub_id']
        db.commit()
        return pub_id
    except Exception:
        db.rollback()
        raise


def db_update_publisher(pub_id: int, name: str, othername: str = None,
                        location: str = None, description: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_publisher
               SET pub_name = %s, pub_othername = %s,
                   pub_location = %s, pub_description = %s
             WHERE pub_id = %s
        """, (name, othername or None, location or None, description or None, pub_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_publisher(pub_id: int) -> bool:
    """Delete a publisher. Raises if still referenced by books/articles (FK SET NULL won't raise,
    so this always succeeds unless the row doesn't exist)."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_publisher WHERE pub_id = %s", (pub_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_find_publishers_by_name_fuzzy(name: str) -> list:
    """Fuzzy candidates for AI matching: publishers whose name contains the first significant word."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    words = [w for w in name.split() if len(w) > 3]
    keyword = words[0] if words else name[:6]
    cur.execute("""
        SELECT pub_id, pub_name
          FROM nightsquirrel.tbl_r_publisher
         WHERE LOWER(pub_name) LIKE LOWER(%s)
         ORDER BY pub_name
         LIMIT 20
    """, (f'%{keyword}%',))
    return cur.fetchall()


def db_find_publisher_by_name(name: str) -> int | None:
    """Case-insensitive exact match on pub_name. Returns pub_id or None."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pub_id FROM nightsquirrel.tbl_r_publisher
         WHERE LOWER(pub_name) = LOWER(%s)
         LIMIT 1
    """, (name,))
    row = cur.fetchone()
    return row['pub_id'] if row else None


# =============================================================================
# BOOKS
# =============================================================================

def db_get_book(bok_id: int) -> Optional[dict]:
    """Return a book row with joined person/publisher names for display."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT b.*,
               CONCAT_WS(' ', a1.per_firstname, a1.per_familyname) AS bok_author1_name,
               CONCAT_WS(' ', a2.per_firstname, a2.per_familyname) AS bok_author2_name,
               CONCAT_WS(' ', e1.per_firstname, e1.per_familyname) AS bok_editor1_name,
               CONCAT_WS(' ', e2.per_firstname, e2.per_familyname) AS bok_editor2_name,
               CONCAT_WS(' ', t1.per_firstname, t1.per_familyname) AS bok_translator1_name,
               CONCAT_WS(' ', t2.per_firstname, t2.per_familyname) AS bok_translator2_name,
               p.pub_name
          FROM nightsquirrel.tbl_r_book b
          LEFT JOIN nightsquirrel.tbl_r_person a1 ON a1.per_id = b.bok_author1_per_id
          LEFT JOIN nightsquirrel.tbl_r_person a2 ON a2.per_id = b.bok_author2_per_id
          LEFT JOIN nightsquirrel.tbl_r_person e1 ON e1.per_id = b.bok_editor1_per_id
          LEFT JOIN nightsquirrel.tbl_r_person e2 ON e2.per_id = b.bok_editor2_per_id
          LEFT JOIN nightsquirrel.tbl_r_person t1 ON t1.per_id = b.bok_translator1_per_id
          LEFT JOIN nightsquirrel.tbl_r_person t2 ON t2.per_id = b.bok_translator2_per_id
          LEFT JOIN nightsquirrel.tbl_r_publisher p ON p.pub_id = b.pub_id
         WHERE b.bok_id = %s
    """, (bok_id,))
    return cur.fetchone()


def db_create_book(usr_id: int, title: str = None, subtitle: str = None,
                   author1_per_id: int = None, author2_per_id: int = None,
                   author_other: str = None, author_etal: bool = False,
                   editor1_per_id: int = None, editor2_per_id: int = None,
                   editor_other: str = None, editor_etal: bool = False,
                   translator1_per_id: int = None, translator2_per_id: int = None,
                   translator_other: str = None, translator_etal: bool = False,
                   year: int = None, pub_id: int = None, location: str = None,
                   isbn: str = None, edition: str = None,
                   language: str = None, link: str = None,
                   pages: int = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_book (
                usr_id, bok_title, bok_subtitle,
                bok_author1_per_id, bok_author2_per_id, bok_author_other, bok_author_etal,
                bok_editor1_per_id, bok_editor2_per_id, bok_editor_other, bok_editor_etal,
                bok_translator1_per_id, bok_translator2_per_id,
                bok_translator_other, bok_translator_etal,
                bok_year, pub_id, bok_location, bok_isbn,
                bok_edition, bok_language, bok_pages, bok_link
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            ) RETURNING bok_id
        """, (
            usr_id, title or None, subtitle or None,
            author1_per_id, author2_per_id, author_other or None, author_etal,
            editor1_per_id, editor2_per_id, editor_other or None, editor_etal,
            translator1_per_id, translator2_per_id,
            translator_other or None, translator_etal,
            year, pub_id, location or None, isbn or None,
            edition or None, language or None, pages, link or None,
        ))
        bok_id = cur.fetchone()['bok_id']
        db.commit()
        return bok_id
    except Exception:
        db.rollback()
        raise


def db_update_book(bok_id: int, title: str = None, subtitle: str = None,
                   author1_per_id: int = None, author2_per_id: int = None,
                   author_other: str = None, author_etal: bool = False,
                   editor1_per_id: int = None, editor2_per_id: int = None,
                   editor_other: str = None, editor_etal: bool = False,
                   translator1_per_id: int = None, translator2_per_id: int = None,
                   translator_other: str = None, translator_etal: bool = False,
                   year: int = None, pub_id: int = None, location: str = None,
                   isbn: str = None, edition: str = None,
                   language: str = None, link: str = None,
                   pages: int = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_book SET
                bok_title = %s, bok_subtitle = %s,
                bok_author1_per_id = %s, bok_author2_per_id = %s,
                bok_author_other = %s,   bok_author_etal = %s,
                bok_editor1_per_id = %s, bok_editor2_per_id = %s,
                bok_editor_other = %s,   bok_editor_etal = %s,
                bok_translator1_per_id = %s, bok_translator2_per_id = %s,
                bok_translator_other = %s,   bok_translator_etal = %s,
                bok_year = %s, pub_id = %s, bok_location = %s, bok_isbn = %s,
                bok_edition = %s, bok_language = %s, bok_pages = %s, bok_link = %s
            WHERE bok_id = %s
        """, (
            title or None, subtitle or None,
            author1_per_id, author2_per_id, author_other or None, author_etal,
            editor1_per_id, editor2_per_id, editor_other or None, editor_etal,
            translator1_per_id, translator2_per_id,
            translator_other or None, translator_etal,
            year, pub_id, location or None, isbn or None,
            edition or None, language or None, pages, link or None,
            bok_id,
        ))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_book(bok_id: int) -> bool:
    """Delete a book. Cascades to any tbl_r_reference pointing to it."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_book WHERE bok_id = %s", (bok_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


# =============================================================================
# ARTICLES
# =============================================================================

def db_get_article(art_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.*,
               CONCAT_WS(' ', a1.per_firstname, a1.per_familyname) AS art_author1_name,
               CONCAT_WS(' ', a2.per_firstname, a2.per_familyname) AS art_author2_name,
               CONCAT_WS(' ', e1.per_firstname, e1.per_familyname) AS art_editor1_name,
               CONCAT_WS(' ', e2.per_firstname, e2.per_familyname) AS art_editor2_name,
               p.pub_name
          FROM nightsquirrel.tbl_r_article a
          LEFT JOIN nightsquirrel.tbl_r_person a1 ON a1.per_id = a.art_author1_per_id
          LEFT JOIN nightsquirrel.tbl_r_person a2 ON a2.per_id = a.art_author2_per_id
          LEFT JOIN nightsquirrel.tbl_r_person e1 ON e1.per_id = a.art_editor1_per_id
          LEFT JOIN nightsquirrel.tbl_r_person e2 ON e2.per_id = a.art_editor2_per_id
          LEFT JOIN nightsquirrel.tbl_r_publisher p ON p.pub_id = a.pub_id
         WHERE a.art_id = %s
    """, (art_id,))
    return cur.fetchone()


def db_create_article(usr_id: int, title: str = None,
                      author1_per_id: int = None, author2_per_id: int = None,
                      author_other: str = None, author_etal: bool = False,
                      editor1_per_id: int = None, editor2_per_id: int = None,
                      editor_other: str = None, editor_etal: bool = False,
                      date: str = None, pub_id: int = None, location: str = None,
                      doi: str = None, container: str = None, issue: str = None,
                      language: str = None, link: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_article (
                usr_id, art_title,
                art_author1_per_id, art_author2_per_id, art_author_other, art_author_etal,
                art_editor1_per_id, art_editor2_per_id, art_editor_other, art_editor_etal,
                art_date, pub_id, art_location, art_doi,
                art_container, art_issue, art_language, art_link
            ) VALUES (
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            ) RETURNING art_id
        """, (
            usr_id, title or None,
            author1_per_id, author2_per_id, author_other or None, author_etal,
            editor1_per_id, editor2_per_id, editor_other or None, editor_etal,
            date or None, pub_id, location or None, doi or None,
            container or None, issue or None, language or None, link or None,
        ))
        art_id = cur.fetchone()['art_id']
        db.commit()
        return art_id
    except Exception:
        db.rollback()
        raise


def db_update_article(art_id: int, title: str = None,
                      author1_per_id: int = None, author2_per_id: int = None,
                      author_other: str = None, author_etal: bool = False,
                      editor1_per_id: int = None, editor2_per_id: int = None,
                      editor_other: str = None, editor_etal: bool = False,
                      date: str = None, pub_id: int = None, location: str = None,
                      doi: str = None, container: str = None, issue: str = None,
                      language: str = None, link: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_article SET
                art_title = %s,
                art_author1_per_id = %s, art_author2_per_id = %s,
                art_author_other = %s,   art_author_etal = %s,
                art_editor1_per_id = %s, art_editor2_per_id = %s,
                art_editor_other = %s,   art_editor_etal = %s,
                art_date = %s, pub_id = %s, art_location = %s, art_doi = %s,
                art_container = %s, art_issue = %s, art_language = %s, art_link = %s
            WHERE art_id = %s
        """, (
            title or None,
            author1_per_id, author2_per_id, author_other or None, author_etal,
            editor1_per_id, editor2_per_id, editor_other or None, editor_etal,
            date or None, pub_id, location or None, doi or None,
            container or None, issue or None, language or None, link or None,
            art_id,
        ))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_article(art_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_article WHERE art_id = %s", (art_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


# =============================================================================
# VIDEOS
# =============================================================================

def db_get_video(vid_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_video WHERE vid_id = %s", (vid_id,))
    return cur.fetchone()


def db_create_video(usr_id: int, title: str = None, editor: str = None,
                    date: str = None, platform: str = None,
                    language: str = None, link: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_video
                (usr_id, vid_title, vid_editor, vid_date, vid_platform, vid_language, vid_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING vid_id
        """, (usr_id, title or None, editor or None, date or None,
              platform or None, language or None, link or None))
        vid_id = cur.fetchone()['vid_id']
        db.commit()
        return vid_id
    except Exception:
        db.rollback()
        raise


def db_update_video(vid_id: int, title: str = None, editor: str = None,
                    date: str = None, platform: str = None,
                    language: str = None, link: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_video
               SET vid_title = %s, vid_editor = %s, vid_date = %s,
                   vid_platform = %s, vid_language = %s, vid_link = %s
             WHERE vid_id = %s
        """, (title or None, editor or None, date or None,
              platform or None, language or None, link or None, vid_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_video(vid_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_video WHERE vid_id = %s", (vid_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


# =============================================================================
# WEBLINKS
# =============================================================================

def db_get_weblink(wlk_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_weblink WHERE wlk_id = %s", (wlk_id,))
    return cur.fetchone()


def db_create_weblink(usr_id: int, title: str = None, editor: str = None,
                      date: str = None, platform: str = None,
                      language: str = None, link: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_weblink
                (usr_id, wlk_title, wlk_editor, wlk_date, wlk_platform, wlk_language, wlk_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING wlk_id
        """, (usr_id, title or None, editor or None, date or None,
              platform or None, language or None, link or None))
        wlk_id = cur.fetchone()['wlk_id']
        db.commit()
        return wlk_id
    except Exception:
        db.rollback()
        raise


def db_update_weblink(wlk_id: int, title: str = None, editor: str = None,
                      date: str = None, platform: str = None,
                      language: str = None, link: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_weblink
               SET wlk_title = %s, wlk_editor = %s, wlk_date = %s,
                   wlk_platform = %s, wlk_language = %s, wlk_link = %s
             WHERE wlk_id = %s
        """, (title or None, editor or None, date or None,
              platform or None, language or None, link or None, wlk_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_delete_weblink(wlk_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM nightsquirrel.tbl_r_weblink WHERE wlk_id = %s", (wlk_id,))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


# =============================================================================
# REFERENCE IMAGES (cover / thumbnail stored in S3)
# =============================================================================

def db_create_reference_image(filename: str, s3_key: str,
                               content_type: str, size_bytes: int) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_image
                (img_filename, img_s3_key, img_content_type, img_size_bytes)
            VALUES (%s, %s, %s, %s)
            RETURNING img_id
        """, (filename, s3_key, content_type, size_bytes))
        img_id = cur.fetchone()['img_id']
        db.commit()
        return img_id
    except Exception:
        db.rollback()
        raise


def db_delete_reference_image(img_id: int) -> Optional[str]:
    """Delete an image record. Returns the S3 key for cleanup, or None if not found."""
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_r_image WHERE img_id = %s RETURNING img_s3_key
        """, (img_id,))
        row = cur.fetchone()
        db.commit()
        return row['img_s3_key'] if row else None
    except Exception:
        db.rollback()
        raise


# =============================================================================
# REFERENCES
# =============================================================================

_REF_LIST_QUERY = """
    SELECT r.ref_id, r.rtp_id, r.usr_id, r.ref_is_library, r.ref_note,
           r.ref_cover_img_id, r.ref_thumbnail_img_id,
           r.ref_created_at, r.ref_updated_at, r.ref_needs_review,
           r.ref_is_current, r.ref_is_recent, r.ref_is_crucial,
           rt.rtp_name_ita, rt.rtp_name_eng,
           COALESCE(b.bok_title, a.art_title, v.vid_title, w.wlk_title) AS ref_title,
           b.bok_subtitle AS ref_subtitle,
           COALESCE(
               CONCAT_WS(' ', pb.per_firstname, pb.per_familyname),
               CONCAT_WS(' ', pa.per_firstname, pa.per_familyname)
           ) AS ref_author1_name,
           COALESCE(b.bok_author1_per_id, a.art_author1_per_id) AS ref_author1_per_id,
           COALESCE(pb.per_won_nobel, pa.per_won_nobel) AS ref_author1_won_nobel,
           COALESCE(b.bok_year::text, a.art_date) AS ref_year,
           ci.img_s3_key  AS cover_s3_key,
           ti.img_s3_key  AS thumbnail_s3_key,
           u.usr_name     AS owner_name,
           u.usr_email    AS owner_email
      FROM nightsquirrel.tbl_r_reference r
      JOIN nightsquirrel.tbl_r_reference_type rt ON rt.rtp_id = r.rtp_id
      LEFT JOIN nightsquirrel.tbl_u_user       u  ON u.usr_id  = r.usr_id
      LEFT JOIN nightsquirrel.tbl_r_book    b  ON b.bok_id  = r.ref_bok_id
      LEFT JOIN nightsquirrel.tbl_r_article a  ON a.art_id  = r.ref_art_id
      LEFT JOIN nightsquirrel.tbl_r_video   v  ON v.vid_id  = r.ref_vid_id
      LEFT JOIN nightsquirrel.tbl_r_weblink w  ON w.wlk_id  = r.ref_wlk_id
      LEFT JOIN nightsquirrel.tbl_r_person pb  ON pb.per_id = b.bok_author1_per_id
      LEFT JOIN nightsquirrel.tbl_r_person pa  ON pa.per_id = a.art_author1_per_id
      LEFT JOIN nightsquirrel.tbl_r_image  ci  ON ci.img_id = r.ref_cover_img_id
      LEFT JOIN nightsquirrel.tbl_r_image  ti  ON ti.img_id = r.ref_thumbnail_img_id
"""


def db_list_references(library_only: bool = False, rtp_id: int = None,
                       usr_id: int = None, q: str = None,
                       needs_review: bool = None,
                       crucial_only: bool = False) -> list:
    """List references with summary fields. Supports filtering by library flag, type, owner, title, needs_review, crucial."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if library_only:
        conditions.append("r.ref_is_library = true")
    if rtp_id is not None:
        conditions.append("r.rtp_id = %s")
        params.append(rtp_id)
    if usr_id is not None:
        conditions.append("r.usr_id = %s")
        params.append(usr_id)
    if q:
        q_like = f'%{q.lower()}%'
        conditions.append("""
            (
                LOWER(COALESCE(b.bok_title, a.art_title, v.vid_title, w.wlk_title, '')) LIKE %s
                OR LOWER(COALESCE(b.bok_subtitle, '')) LIKE %s
                OR EXISTS (
                    SELECT 1 FROM nightsquirrel.tbl_r_person p2
                    WHERE p2.per_id IN (
                        b.bok_author1_per_id, b.bok_author2_per_id,
                        b.bok_editor1_per_id, b.bok_editor2_per_id,
                        b.bok_translator1_per_id, b.bok_translator2_per_id,
                        a.art_author1_per_id, a.art_author2_per_id,
                        a.art_editor1_per_id, a.art_editor2_per_id
                    )
                    AND LOWER(CONCAT_WS(' ', p2.per_firstname, p2.per_familyname)) LIKE %s
                )
            )
        """)
        params.extend([q_like, q_like, q_like])
    if needs_review is not None:
        conditions.append("r.ref_needs_review = %s")
        params.append(needs_review)
    if crucial_only:
        conditions.append("r.ref_is_crucial = true")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"{_REF_LIST_QUERY} {where} ORDER BY r.ref_created_at DESC", params)
    return cur.fetchall()


def db_get_reference(ref_id: int) -> Optional[dict]:
    """Return a reference row with summary fields (title, author, year, image S3 keys)."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"{_REF_LIST_QUERY} WHERE r.ref_id = %s", (ref_id,))
    return cur.fetchone()


def db_list_references_by_person(per_id: int, library_only: bool = True) -> list:
    """Return references linked to the given person (any author/editor/translator role).
    library_only=True  → only ref_is_library references (public view)
    library_only=False → all references regardless of visibility (admin view)
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    library_clause = "r.ref_is_library = true AND" if library_only else ""
    cur.execute(f"""
        {_REF_LIST_QUERY}
        WHERE {library_clause} (
              b.bok_author1_per_id = %(p)s OR b.bok_author2_per_id = %(p)s
           OR b.bok_editor1_per_id = %(p)s OR b.bok_editor2_per_id = %(p)s
           OR b.bok_translator1_per_id = %(p)s OR b.bok_translator2_per_id = %(p)s
           OR a.art_author1_per_id = %(p)s OR a.art_author2_per_id = %(p)s
           OR a.art_editor1_per_id = %(p)s OR a.art_editor2_per_id = %(p)s
          )
        ORDER BY r.ref_created_at DESC
    """, {'p': per_id})
    return cur.fetchall()


def db_list_references_by_tag(tag_id: int) -> list:
    """Return all library references that have the given tag attached."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"""
        {_REF_LIST_QUERY}
        JOIN nightsquirrel.tbl_t_tag2reference j ON j.ref_id = r.ref_id
        WHERE r.ref_is_library = true
          AND j.tag_id = %(t)s
        ORDER BY r.ref_created_at DESC
    """, {'t': tag_id})
    return cur.fetchall()


def db_list_library_persons_with_refs(q: str = None) -> list:
    """Return [{person: {...}, refs: [...]}, ...] for all persons with ≥1 library reference, sorted by family name."""
    from collections import OrderedDict
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    params = []
    name_filter = ""
    if q:
        name_filter = """WHERE (
            LOWER(COALESCE(p.per_firstname,'') || ' ' || COALESCE(p.per_familyname,'')) LIKE %s
            OR LOWER(COALESCE(p.per_familyname,'') || ' ' || COALESCE(p.per_firstname,'')) LIKE %s
        )"""
        q_like = f'%{q.lower()}%'
        params = [q_like, q_like]
    cur.execute(f"""
        WITH person_ref_links AS (
            SELECT b.bok_author1_per_id     AS per_id, r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_author1_per_id     IS NOT NULL
            UNION SELECT b.bok_author2_per_id,    r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_author2_per_id     IS NOT NULL
            UNION SELECT b.bok_editor1_per_id,    r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_editor1_per_id     IS NOT NULL
            UNION SELECT b.bok_editor2_per_id,    r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_editor2_per_id     IS NOT NULL
            UNION SELECT b.bok_translator1_per_id, r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_translator1_per_id IS NOT NULL
            UNION SELECT b.bok_translator2_per_id, r.ref_id FROM nightsquirrel.tbl_r_book b JOIN nightsquirrel.tbl_r_reference r ON r.ref_bok_id = b.bok_id AND r.ref_is_library = true WHERE b.bok_translator2_per_id IS NOT NULL
            UNION SELECT a.art_author1_per_id,    r.ref_id FROM nightsquirrel.tbl_r_article a JOIN nightsquirrel.tbl_r_reference r ON r.ref_art_id = a.art_id AND r.ref_is_library = true WHERE a.art_author1_per_id    IS NOT NULL
            UNION SELECT a.art_author2_per_id,    r.ref_id FROM nightsquirrel.tbl_r_article a JOIN nightsquirrel.tbl_r_reference r ON r.ref_art_id = a.art_id AND r.ref_is_library = true WHERE a.art_author2_per_id    IS NOT NULL
            UNION SELECT a.art_editor1_per_id,    r.ref_id FROM nightsquirrel.tbl_r_article a JOIN nightsquirrel.tbl_r_reference r ON r.ref_art_id = a.art_id AND r.ref_is_library = true WHERE a.art_editor1_per_id    IS NOT NULL
            UNION SELECT a.art_editor2_per_id,    r.ref_id FROM nightsquirrel.tbl_r_article a JOIN nightsquirrel.tbl_r_reference r ON r.ref_art_id = a.art_id AND r.ref_is_library = true WHERE a.art_editor2_per_id    IS NOT NULL
        ),
        ref_summary AS (
            SELECT r.ref_id,
                   COALESCE(b.bok_title, a.art_title, v.vid_title, w.wlk_title) AS ref_title,
                   b.bok_subtitle AS ref_subtitle,
                   ti.img_s3_key  AS thumbnail_s3_key,
                   rt.rtp_name_eng,
                   COALESCE(b.bok_year::text, a.art_date) AS ref_year
              FROM nightsquirrel.tbl_r_reference r
              JOIN nightsquirrel.tbl_r_reference_type rt ON rt.rtp_id = r.rtp_id
              LEFT JOIN nightsquirrel.tbl_r_book    b  ON b.bok_id  = r.ref_bok_id
              LEFT JOIN nightsquirrel.tbl_r_article a  ON a.art_id  = r.ref_art_id
              LEFT JOIN nightsquirrel.tbl_r_video   v  ON v.vid_id  = r.ref_vid_id
              LEFT JOIN nightsquirrel.tbl_r_weblink w  ON w.wlk_id  = r.ref_wlk_id
              LEFT JOIN nightsquirrel.tbl_r_image   ti ON ti.img_id = r.ref_thumbnail_img_id
        )
        SELECT p.per_id, p.per_firstname, p.per_familyname,
               p.per_caption_ita, p.per_caption_eng, p.per_won_nobel,
               rs.ref_id, rs.ref_title, rs.ref_subtitle,
               rs.thumbnail_s3_key, rs.rtp_name_eng, rs.ref_year
          FROM nightsquirrel.tbl_r_person p
          JOIN person_ref_links prl ON prl.per_id = p.per_id
          JOIN ref_summary      rs  ON rs.ref_id  = prl.ref_id
        {name_filter}
        ORDER BY p.per_familyname, p.per_firstname, rs.ref_title
    """, params)
    persons: OrderedDict = OrderedDict()
    for row in cur.fetchall():
        pid = row['per_id']
        if pid not in persons:
            persons[pid] = {
                'person': {k: row[k] for k in ('per_id', 'per_firstname', 'per_familyname',
                                                'per_caption_ita', 'per_caption_eng',
                                                'per_won_nobel')},
                'refs': [],
            }
        persons[pid]['refs'].append({k: row[k] for k in
            ('ref_id', 'ref_title', 'ref_subtitle', 'thumbnail_s3_key', 'rtp_name_eng', 'ref_year')})
    return list(persons.values())


def db_get_reference_typed_entity(ref_id: int) -> Optional[dict]:
    """Return the typed entity (book/article/video/weblink) for a reference, with full detail."""
    ref = db_get_reference(ref_id)
    if not ref:
        return None
    if ref['ref_bok_id'] if 'ref_bok_id' in ref else None:
        pass  # handled below via direct lookup
    # Re-fetch with FK columns
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT ref_bok_id, ref_art_id, ref_vid_id, ref_wlk_id
          FROM nightsquirrel.tbl_r_reference WHERE ref_id = %s
    """, (ref_id,))
    fks = cur.fetchone()
    if not fks:
        return None
    if fks['ref_bok_id']:
        return db_get_book(fks['ref_bok_id'])
    if fks['ref_art_id']:
        return db_get_article(fks['ref_art_id'])
    if fks['ref_vid_id']:
        return db_get_video(fks['ref_vid_id'])
    if fks['ref_wlk_id']:
        return db_get_weblink(fks['ref_wlk_id'])
    return None


def db_get_reference_fks(ref_id: int) -> Optional[dict]:
    """Return just the typed FK columns for a reference (for routing to edit forms)."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT ref_id, rtp_id, usr_id, ref_bok_id, ref_art_id, ref_vid_id, ref_wlk_id,
               ref_cover_img_id, ref_thumbnail_img_id, ref_is_library, ref_note, ref_needs_review
          FROM nightsquirrel.tbl_r_reference WHERE ref_id = %s
    """, (ref_id,))
    return cur.fetchone()


def db_create_reference(rtp_id: int, usr_id: int,
                        ref_bok_id: int = None, ref_art_id: int = None,
                        ref_vid_id: int = None, ref_wlk_id: int = None,
                        is_library: bool = False, note: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_reference
                (rtp_id, usr_id, ref_bok_id, ref_art_id, ref_vid_id, ref_wlk_id,
                 ref_is_library, ref_note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING ref_id
        """, (rtp_id, usr_id, ref_bok_id, ref_art_id, ref_vid_id, ref_wlk_id,
              is_library, note or None))
        ref_id = cur.fetchone()['ref_id']
        db.commit()
        return ref_id
    except Exception:
        db.rollback()
        raise


def db_update_reference_meta(ref_id: int, is_library: bool, note: str = None) -> bool:
    """Update only the reference-level metadata (library flag, note)."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_reference
               SET ref_is_library = %s, ref_note = %s
             WHERE ref_id = %s
        """, (is_library, note or None, ref_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_set_reference_images(ref_id: int,
                             cover_img_id: int = None,
                             thumbnail_img_id: int = None) -> bool:
    """Update cover and/or thumbnail image FKs on a reference."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_r_reference
               SET ref_cover_img_id = %s, ref_thumbnail_img_id = %s
             WHERE ref_id = %s
        """, (cover_img_id, thumbnail_img_id, ref_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


def db_clear_ref_needs_review(ref_id: int) -> bool:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE nightsquirrel.tbl_r_reference SET ref_needs_review = FALSE WHERE ref_id = %s",
        (ref_id,))
    db.commit()
    return cur.rowcount > 0


def db_set_ref_needs_review(ref_id: int) -> None:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE nightsquirrel.tbl_r_reference SET ref_needs_review = TRUE WHERE ref_id = %s",
        (ref_id,))
    db.commit()


def db_toggle_ref_flag(ref_id: int, flag: str) -> bool:
    """Toggle one of ref_is_current, ref_is_recent, ref_is_crucial."""
    allowed = {'ref_is_current', 'ref_is_recent', 'ref_is_crucial'}
    if flag not in allowed:
        raise ValueError(f"Invalid flag: {flag}")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        f"UPDATE nightsquirrel.tbl_r_reference SET {flag} = NOT {flag} WHERE ref_id = %s",
        (ref_id,))
    db.commit()
    return cur.rowcount > 0


def db_list_leo_reading() -> tuple:
    """Return (current_refs, recent_refs). Recent excludes refs already in current."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"{_REF_LIST_QUERY} WHERE r.ref_is_current = TRUE ORDER BY r.ref_updated_at DESC")
    current = cur.fetchall()
    cur.execute(f"""
        {_REF_LIST_QUERY}
        WHERE r.ref_is_recent = TRUE AND r.ref_is_current = FALSE
        ORDER BY r.ref_updated_at DESC
    """)
    recent = cur.fetchall()
    return current, recent


def db_delete_reference(ref_id: int) -> dict:
    """Delete a reference and its underlying typed entity.

    Strategy: delete the typed entity first — the FK ON DELETE CASCADE removes
    the reference row and all junction rows automatically.
    Images are deleted separately so their S3 keys can be returned for cleanup.

    Returns {'cover_s3_key': ..., 'thumbnail_s3_key': ...} (either may be None).
    """
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        # Capture FKs before anything is deleted
        cur.execute("""
            SELECT rtp_id, ref_bok_id, ref_art_id, ref_vid_id, ref_wlk_id,
                   ref_cover_img_id, ref_thumbnail_img_id
              FROM nightsquirrel.tbl_r_reference WHERE ref_id = %s
        """, (ref_id,))
        row = cur.fetchone()
        if not row:
            db.commit()
            return {'cover_s3_key': None, 'thumbnail_s3_key': None}

        cover_id     = row['ref_cover_img_id']
        thumbnail_id = row['ref_thumbnail_img_id']

        # Delete typed entity → CASCADE deletes reference + junctions
        if row['ref_bok_id']:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_book    WHERE bok_id = %s", (row['ref_bok_id'],))
        elif row['ref_art_id']:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_article WHERE art_id = %s", (row['ref_art_id'],))
        elif row['ref_vid_id']:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_video   WHERE vid_id = %s", (row['ref_vid_id'],))
        elif row['ref_wlk_id']:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_weblink WHERE wlk_id = %s", (row['ref_wlk_id'],))

        # Delete image records (reference row is gone, no FK issue)
        cover_s3 = thumbnail_s3 = None
        if cover_id:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_image WHERE img_id = %s RETURNING img_s3_key",
                        (cover_id,))
            r = cur.fetchone()
            cover_s3 = r['img_s3_key'] if r else None
        if thumbnail_id and thumbnail_id != cover_id:
            cur.execute("DELETE FROM nightsquirrel.tbl_r_image WHERE img_id = %s RETURNING img_s3_key",
                        (thumbnail_id,))
            r = cur.fetchone()
            thumbnail_s3 = r['img_s3_key'] if r else None

        db.commit()
        return {'cover_s3_key': cover_s3, 'thumbnail_s3_key': thumbnail_s3}
    except Exception:
        db.rollback()
        raise


# =============================================================================
# JUNCTION: reference ↔ question
# =============================================================================

def db_list_references_for_question(qtn_id: int) -> list:
    """Return all references attached to a question, ordered by seqno."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"""
        {_REF_LIST_QUERY}
        JOIN nightsquirrel.tbl_r_reference2question j ON j.ref_id = r.ref_id
         WHERE j.qtn_id = %s
         ORDER BY j.r2q_seqno, r.ref_created_at
    """, (qtn_id,))
    return cur.fetchall()


def db_attach_reference_to_question(ref_id: int, qtn_id: int, seqno: int = 1) -> bool:
    """Attach a reference to a question. Silently ignored if already attached."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_reference2question (ref_id, qtn_id, r2q_seqno)
            VALUES (%s, %s, %s)
            ON CONFLICT (ref_id, qtn_id) DO NOTHING
        """, (ref_id, qtn_id, seqno))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def db_detach_reference_from_question(ref_id: int, qtn_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_r_reference2question
             WHERE ref_id = %s AND qtn_id = %s
        """, (ref_id, qtn_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise


# =============================================================================
# JUNCTION: reference ↔ answer
# =============================================================================

def db_list_references_for_answer(ans_id: int) -> list:
    """Return all references attached to an answer, ordered by seqno."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"""
        {_REF_LIST_QUERY}
        JOIN nightsquirrel.tbl_r_reference2answer j ON j.ref_id = r.ref_id
         WHERE j.ans_id = %s
         ORDER BY j.r2a_seqno, r.ref_created_at
    """, (ans_id,))
    return cur.fetchall()


def db_attach_reference_to_answer(ref_id: int, ans_id: int, seqno: int = 1) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_r_reference2answer (ref_id, ans_id, r2a_seqno)
            VALUES (%s, %s, %s)
            ON CONFLICT (ref_id, ans_id) DO NOTHING
        """, (ref_id, ans_id, seqno))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def db_detach_reference_from_answer(ref_id: int, ans_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_r_reference2answer
             WHERE ref_id = %s AND ans_id = %s
        """, (ref_id, ans_id))
        db.commit()
        return cur.rowcount > 0
    except Exception:
        db.rollback()
        raise
