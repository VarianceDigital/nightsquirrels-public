from psycopg2.extras import RealDictCursor
from .db import get_db
from typing import Optional
from datetime import datetime, timezone


# =============================================================================
# INTEREST CRUD (admin only)
# =============================================================================

def db_list_interests(q: str = None) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    if q:
        cur.execute("""
            SELECT i.uit_id, i.uit_name_ita, i.uit_name_eng, i.uit_type,
                   i.uit_created_at, i.uit_updated_at,
                   COUNT(DISTINCT j.usr_id) AS usage_users
              FROM nightsquirrel.tbl_u_interest i
              LEFT JOIN nightsquirrel.tbl_u_interest2user j ON j.uit_id = i.uit_id
             WHERE i.uit_name_ita ILIKE %s
                OR i.uit_name_eng ILIKE %s
             GROUP BY i.uit_id
             ORDER BY i.uit_name_eng
        """, (f'%{q}%', f'%{q}%'))
    else:
        cur.execute("""
            SELECT i.uit_id, i.uit_name_ita, i.uit_name_eng, i.uit_type,
                   i.uit_created_at, i.uit_updated_at,
                   COUNT(DISTINCT j.usr_id) AS usage_users
              FROM nightsquirrel.tbl_u_interest i
              LEFT JOIN nightsquirrel.tbl_u_interest2user j ON j.uit_id = i.uit_id
             GROUP BY i.uit_id
             ORDER BY i.uit_name_eng
        """)
    return cur.fetchall()


def db_get_interest(uit_id: int) -> Optional[dict]:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT uit_id, uit_name_ita, uit_name_eng, uit_type,
               uit_created_at, uit_updated_at
          FROM nightsquirrel.tbl_u_interest
         WHERE uit_id = %s
    """, (uit_id,))
    return cur.fetchone()


def db_create_interest(name_ita: str, name_eng: str, uit_type: str = None) -> int:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_u_interest
                   (uit_name_ita, uit_name_eng, uit_type)
            VALUES (%s, %s, %s)
            RETURNING uit_id
        """, (name_ita, name_eng, uit_type or None))
        uit_id = cur.fetchone()[0]
        db.commit()
        return uit_id
    except Exception:
        db.rollback()
        raise


def db_update_interest(uit_id: int, name_ita: str, name_eng: str,
                       uit_type: str = None) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_u_interest
               SET uit_name_ita = %s,
                   uit_name_eng = %s,
                   uit_type     = %s
             WHERE uit_id = %s
        """, (name_ita, name_eng, uit_type or None, uit_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_delete_interest(uit_id: int) -> bool:
    """Delete an interest. Junction rows are removed automatically via CASCADE."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_u_interest
             WHERE uit_id = %s
        """, (uit_id,))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# =============================================================================
# JUNCTION — user ↔ interest
# =============================================================================

def db_list_interests_for_user(usr_id: int) -> list:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT i.uit_id, i.uit_name_ita, i.uit_name_eng, i.uit_type
          FROM nightsquirrel.tbl_u_interest i
          JOIN nightsquirrel.tbl_u_interest2user j ON j.uit_id = i.uit_id
         WHERE j.usr_id = %s
         ORDER BY i.uit_name_eng
    """, (usr_id,))
    return cur.fetchall()


def db_list_available_interests_for_user(usr_id: int) -> list:
    """Interests not yet attached to this user."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT i.uit_id, i.uit_name_ita, i.uit_name_eng, i.uit_type
          FROM nightsquirrel.tbl_u_interest i
         WHERE i.uit_id NOT IN (
               SELECT uit_id
                 FROM nightsquirrel.tbl_u_interest2user
                WHERE usr_id = %s
         )
         ORDER BY i.uit_name_eng
    """, (usr_id,))
    return cur.fetchall()


def db_attach_interest_to_user(uit_id: int, usr_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            INSERT INTO nightsquirrel.tbl_u_interest2user (uit_id, usr_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (uit_id, usr_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_detach_interest_from_user(uit_id: int, usr_id: int) -> bool:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            DELETE FROM nightsquirrel.tbl_u_interest2user
             WHERE uit_id = %s AND usr_id = %s
        """, (uit_id, usr_id))
        ok = cur.rowcount == 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


# =============================================================================
# SEED GENERATOR
# =============================================================================

def db_generate_interests_seed() -> str:
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    def sql_val(v):
        if v is None:               return 'NULL'
        if isinstance(v, bool):     return 'true' if v else 'false'
        if isinstance(v, int):      return str(v)
        if isinstance(v, float):    return str(v)
        if isinstance(v, datetime): return "'" + v.isoformat() + "'"
        return "'" + str(v).replace("'", "''") + "'"

    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lines = [
        f'-- {"=" * 60}',
        f'-- NightSquirrel — Interests seed',
        f'-- Generated : {generated}',
        f'-- {"=" * 60}',
        '',
        'DELETE FROM nightsquirrel.tbl_u_interest;',
        '',
    ]

    cur.execute("SELECT * FROM nightsquirrel.tbl_u_interest ORDER BY uit_id")
    rows = cur.fetchall()
    if rows:
        cols     = list(rows[0].keys())
        cols_sql = ', '.join(cols)
        for row in rows:
            vals = ', '.join(sql_val(row[c]) for c in cols)
            lines.append(
                f'INSERT INTO nightsquirrel.tbl_u_interest ({cols_sql})'
                f' OVERRIDING SYSTEM VALUE VALUES ({vals});'
            )
        lines.append(
            "SELECT setval(pg_get_serial_sequence("
            "'nightsquirrel.tbl_u_interest', 'uit_id'), "
            "COALESCE((SELECT MAX(uit_id) FROM nightsquirrel.tbl_u_interest), 0));"
        )
    else:
        lines.append('-- (no interests)')

    return '\n'.join(lines) + '\n'
