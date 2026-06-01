import json as _json
from datetime import datetime, timezone
from psycopg2.extras import RealDictCursor
from .db import get_db


def db_admin_stats() -> dict:
    """Return a dict of key counts for the admin dashboard."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
          (SELECT COUNT(*) FROM nightsquirrel.tbl_t_ticket
            WHERE tkt_state IN (0,1,2,3))            AS tickets_pending,
          (SELECT COUNT(*) FROM nightsquirrel.tbl_t_ticket
            WHERE tkt_state = 5 AND tutor_usr_id IS NULL) AS tickets_unassigned,
          (SELECT COUNT(*) FROM nightsquirrel.tbl_t_ticket
            WHERE tkt_state IN (6,7))                AS tickets_in_progress,
          (SELECT COUNT(*) FROM nightsquirrel.tbl_t_ticket
            WHERE tkt_state = 8)                     AS tickets_pending_payment,
          (SELECT COUNT(*) FROM nightsquirrel.tbl_p_payment
            WHERE pay_status = 'failed')             AS payments_failed,
          (SELECT COUNT(*) FROM nightsquirrel.tbl_r_reference
            WHERE ref_needs_review = TRUE)           AS refs_to_review
    """)
    return dict(cur.fetchone())


def db_admin_list_tutors():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT usr_id, usr_email, usr_name
        FROM nightsquirrel.tbl_u_user
        WHERE usr_is_tutor = true AND usr_isvalid = true
        ORDER BY COALESCE(usr_name, usr_email)
    """)
    return cur.fetchall()


def db_admin_list_users(q=None):
    """Admin view: all users with role flags. Optional search on email/name."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    where = []
    params = []

    if q:
        where.append("(u.usr_email ILIKE %s OR u.usr_name ILIKE %s)")
        like = f"%{q}%"
        params += [like, like]

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    cur.execute(f"""
        SELECT usr_id, usr_email, usr_name, usr_isvalid, usr_confirmed,
               usr_is_student, usr_is_tutor, usr_is_admin, usr_is_payer,
               usr_timestamp
          FROM nightsquirrel.tbl_u_user u
        {where_sql}
         ORDER BY usr_timestamp DESC
         LIMIT 200
    """, params)
    return cur.fetchall()


def db_admin_update_user_flags(usr_id, usr_isvalid, usr_is_student,
                                usr_is_tutor, usr_is_admin, usr_is_payer):
    """Admin: update validity and role flags for a user."""
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""
            UPDATE nightsquirrel.tbl_u_user
               SET usr_isvalid = %s,
                   usr_is_student = %s,
                   usr_is_tutor = %s,
                   usr_is_admin = %s,
                   usr_is_payer = %s
             WHERE usr_id = %s
        """, (usr_isvalid, usr_is_student, usr_is_tutor, usr_is_admin,
              usr_is_payer, usr_id))
        ok = cur.rowcount >= 1
        db.commit()
        return ok
    except Exception:
        db.rollback()
        raise


def db_admin_list_questions(q=None, state=None, assigned=None):
    """
    Admin view: all questions + ticket info + user owner
    Filters:
      - q: search in title / plaintext
      - state: ticket state
      - assigned: '1' only assigned, '0' only unassigned, None = all
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    where = []
    params = []

    if q:
        where.append("(q.qtn_title ILIKE %s OR c.ctx_plaintext ILIKE %s OR u.usr_email ILIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]

    if state not in (None, ''):
        where.append("t.tkt_state = %s")
        params.append(int(state))

    if assigned == '1':
        where.append("t.tutor_usr_id IS NOT NULL")
    elif assigned == '0':
        where.append("t.tutor_usr_id IS NULL")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    cur.execute(f"""
        SELECT
            q.qtn_id,
            q.qtn_title,
            q.qtn_state,
            q.qtn_created_at,
            q.qtn_updated_at,

            u.usr_id AS owner_usr_id,
            u.usr_email AS owner_email,
            u.usr_name  AS owner_name,

            t.tkt_id,
            t.tkt_state,
            t.tkt_selected_quote_cents,
            t.tkt_quote_note,
            t.tkt_currency,
            t.tutor_usr_id,
            tu.usr_email AS tutor_email,
            tu.usr_name  AS tutor_name

        FROM nightsquirrel.tbl_q_question q
        JOIN nightsquirrel.tbl_u_user u
          ON u.usr_id = q.usr_id
        LEFT JOIN nightsquirrel.tbl_t_ticket t
          ON t.qtn_id = q.qtn_id
        LEFT JOIN nightsquirrel.tbl_u_user tu
          ON tu.usr_id = t.tutor_usr_id
        LEFT JOIN nightsquirrel.tbl_q_complextext c
          ON c.ctx_id = q.ctx_id
        {where_sql}
        ORDER BY q.qtn_created_at DESC
        LIMIT 200
    """, params)

    return cur.fetchall()


def db_admin_list_payments(status=None):
    """Admin view: all payments with ticket/student/payer info, filterable by status."""
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    where = []
    params = []

    if status:
        where.append("p.pay_status = %s")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    cur.execute(f"""
        SELECT p.pay_id, p.tkt_id, p.payer_usr_id,
               p.pay_amount_cents, p.pay_currency, p.pay_status,
               p.pay_error_msg, p.pay_created_at, p.pay_charged_at,
               p.pay_paypal_order_id, p.pay_paypal_capture_id,
               t.tkt_state,
               q.qtn_title, q.qtn_id,
               u_student.usr_email AS student_email,
               u_student.usr_name  AS student_name,
               u_payer.usr_email   AS payer_email,
               u_payer.usr_name    AS payer_name
          FROM nightsquirrel.tbl_p_payment p
          JOIN nightsquirrel.tbl_t_ticket t ON t.tkt_id = p.tkt_id
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = t.qtn_id
          JOIN nightsquirrel.tbl_u_user u_student ON u_student.usr_id = q.usr_id
          JOIN nightsquirrel.tbl_u_user u_payer   ON u_payer.usr_id = p.payer_usr_id
        {where_sql}
         ORDER BY p.pay_created_at DESC
         LIMIT 200
    """, params)
    return cur.fetchall()


def db_admin_retry_payment(pay_id: int):
    """Reset a failed payment back to awaiting_charge. Returns tkt_id or None."""
    db = get_db()
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            UPDATE nightsquirrel.tbl_p_payment
               SET pay_status = 'awaiting_charge',
                   pay_error_msg = NULL
             WHERE pay_id = %s
               AND pay_status = 'failed'
            RETURNING tkt_id
        """, (pay_id,))
        row = cur.fetchone()
        db.commit()
        return row['tkt_id'] if row else None
    except Exception:
        db.rollback()
        raise


def db_get_all_ref_image_keys() -> set:
    """Return the set of all img_s3_key values currently tracked in tbl_r_image."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT img_s3_key FROM nightsquirrel.tbl_r_image")
    return {row[0] for row in cur.fetchall()}


def db_generate_library_seed() -> str:
    """
    Generate a complete SQL seed script for ALL references, persons, publishers,
    images and tags — regardless of ref_is_library — so that a full rebase
    never loses any data.
    Returns a string ready to be saved as 9-library-seed.sql.
    """
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)

    # ── value formatter ───────────────────────────────────────────────────────
    def sql_val(v):
        if v is None:
            return 'NULL'
        if isinstance(v, bool):          # bool before int — bool subclasses int
            return 'true' if v else 'false'
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return str(v)
        if isinstance(v, datetime):
            return "'" + v.isoformat() + "'"
        if isinstance(v, dict):
            return "'" + _json.dumps(v).replace("'", "''") + "'"
        return "'" + str(v).replace("'", "''") + "'"

    lines = []

    # ── section helper ────────────────────────────────────────────────────────
    def section(title, rows, table, pk_col):
        lines.append(f'\n-- {"─" * 60}')
        lines.append(f'-- {title}')
        lines.append(f'-- {"─" * 60}')
        if not rows:
            lines.append('-- (no rows)')
            return
        cols = list(rows[0].keys())
        cols_sql = ', '.join(cols)
        for row in rows:
            vals = ', '.join(sql_val(row[c]) for c in cols)
            lines.append(
                f'INSERT INTO nightsquirrel.{table} ({cols_sql})'
                f' OVERRIDING SYSTEM VALUE VALUES ({vals});'
            )
        lines.append(
            f"SELECT setval(pg_get_serial_sequence("
            f"'nightsquirrel.{table}', '{pk_col}'), "
            f"COALESCE((SELECT MAX({pk_col}) FROM nightsquirrel.{table}), 0));"
        )

    # ── header ────────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT usr_id FROM nightsquirrel.tbl_u_user
        WHERE usr_is_admin = true ORDER BY usr_id LIMIT 1
    """)
    admin_row = cur.fetchone()
    admin_id  = admin_row['usr_id'] if admin_row else '??'
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    lines += [
        f'-- {"=" * 60}',
        f'-- NightSquirrel — References + Tags seed (ALL references)',
        f'-- Generated : {generated}',
        f'-- Admin usr_id used: {admin_id}',
        f'-- IMPORTANT: run AFTER 2b-seed-admin-user.sql,',
        f'--            which must create the admin with usr_id = {admin_id}',
        f'-- {"=" * 60}',
    ]

    # ── 1. All persons ────────────────────────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_person ORDER BY per_id")
    section('Persons', cur.fetchall(), 'tbl_r_person', 'per_id')

    # ── 2. All publishers ─────────────────────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_publisher ORDER BY pub_id")
    section('Publishers', cur.fetchall(), 'tbl_r_publisher', 'pub_id')

    # ── 3. Images used by any reference ──────────────────────────────────────
    cur.execute("""
        SELECT img.* FROM nightsquirrel.tbl_r_image img
        WHERE img.img_id IN (
            SELECT ref_cover_img_id     FROM nightsquirrel.tbl_r_reference
             WHERE ref_cover_img_id IS NOT NULL
            UNION
            SELECT ref_thumbnail_img_id FROM nightsquirrel.tbl_r_reference
             WHERE ref_thumbnail_img_id IS NOT NULL
        )
        ORDER BY img.img_id
    """)
    section('Images', cur.fetchall(), 'tbl_r_image', 'img_id')

    # ── 4–7. All typed entities ───────────────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_book    ORDER BY bok_id")
    section('Books', cur.fetchall(), 'tbl_r_book', 'bok_id')

    cur.execute("SELECT * FROM nightsquirrel.tbl_r_article ORDER BY art_id")
    section('Articles', cur.fetchall(), 'tbl_r_article', 'art_id')

    cur.execute("SELECT * FROM nightsquirrel.tbl_r_video   ORDER BY vid_id")
    section('Videos', cur.fetchall(), 'tbl_r_video', 'vid_id')

    cur.execute("SELECT * FROM nightsquirrel.tbl_r_weblink ORDER BY wlk_id")
    section('Weblinks', cur.fetchall(), 'tbl_r_weblink', 'wlk_id')

    # ── 8. All references ─────────────────────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_r_reference ORDER BY ref_id")
    section('References', cur.fetchall(), 'tbl_r_reference', 'ref_id')

    # ── 9. All tags ───────────────────────────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_t_tag ORDER BY tag_id")
    section('Tags', cur.fetchall(), 'tbl_t_tag', 'tag_id')

    # ── 10. All tag ↔ reference junctions ────────────────────────────────────
    cur.execute("SELECT * FROM nightsquirrel.tbl_t_tag2reference ORDER BY t2r_id")
    section('Tag → Reference junctions', cur.fetchall(), 'tbl_t_tag2reference', 't2r_id')

    return '\n'.join(lines)
