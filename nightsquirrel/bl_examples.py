from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_babel import get_locale, gettext as _
import psycopg2, json

from .auth import admin_required
from .db_examples import (db_list_examples, db_get_example,
                           db_create_example, db_update_example,
                           db_delete_example, db_generate_examples_seed)
from .db_lookup import db_get_questiontypes

bp = Blueprint('bl_examples', __name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_delta(field: str) -> dict:
    raw = request.form.get(field, '').strip()
    try:
        return json.loads(raw) if raw else {'ops': []}
    except (ValueError, TypeError):
        return {'ops': []}


def _int(field: str, default: int = 0) -> int:
    try:
        return int(request.form.get(field, default))
    except (ValueError, TypeError):
        return default


def _str(field: str):
    return (request.form.get(field) or '').strip() or None


# ── public ────────────────────────────────────────────────────────────────────

@bp.route('/examples')
def examples():
    lang    = str(get_locale())[:2]
    grade   = request.args.get('grade', '').strip() or None
    qtypes  = db_get_questiontypes()
    rows    = db_list_examples(lang=lang, published_only=True, grade=grade)
    by_type = {}
    for r in rows:
        by_type.setdefault(r['qtp_id'], []).append(r)
    return render_template('examples/examples.html',
                           mc={'examples': 'active'}, qtypes=qtypes,
                           by_type=by_type, active_grade=grade)


# ── admin CRUD ────────────────────────────────────────────────────────────────

@bp.route('/admin/examples')
@admin_required
def admin_examples():
    rows   = db_list_examples()
    qtypes = db_get_questiontypes()
    return render_template('admin/examples/list.html',
                           mc={'admin': 'active'}, rows=rows, qtypes=qtypes)


@bp.route('/admin/examples/new', methods=['GET', 'POST'])
@admin_required
def admin_new_example():
    qtypes = db_get_questiontypes()
    if request.method == 'POST':
        try:
            db_create_example(
                qtp_id    = _int('qtp_id'),
                lang      = request.form.get('ex_lang', 'it'),
                title     = request.form.get('ex_title', '').strip(),
                subject   = _str('ex_subject'),
                grade     = _str('ex_grade'),
                q_delta   = _parse_delta('ex_q_delta'),
                a_delta   = _parse_delta('ex_a_delta'),
                seqno     = _int('ex_seqno'),
                published = 'ex_published' in request.form,
            )
            flash(_('Example created.'), 'success')
            return redirect(url_for('bl_examples.admin_examples'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/examples/form.html',
                           mc={'admin': 'active'}, row=None, qtypes=qtypes,
                           action=url_for('bl_examples.admin_new_example'))


@bp.route('/admin/examples/<int:ex_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_example(ex_id):
    row    = db_get_example(ex_id)
    qtypes = db_get_questiontypes()
    if not row:
        flash(_('Example not found.'), 'danger')
        return redirect(url_for('bl_examples.admin_examples'))
    if request.method == 'POST':
        try:
            db_update_example(
                ex_id     = ex_id,
                qtp_id    = _int('qtp_id'),
                lang      = request.form.get('ex_lang', 'it'),
                title     = request.form.get('ex_title', '').strip(),
                subject   = _str('ex_subject'),
                grade     = _str('ex_grade'),
                q_delta   = _parse_delta('ex_q_delta'),
                a_delta   = _parse_delta('ex_a_delta'),
                seqno     = _int('ex_seqno'),
                published = 'ex_published' in request.form,
            )
            flash(_('Example updated.'), 'success')
            return redirect(url_for('bl_examples.admin_examples'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/examples/form.html',
                           mc={'admin': 'active'}, row=row, qtypes=qtypes,
                           action=url_for('bl_examples.admin_edit_example',
                                         ex_id=ex_id))


@bp.get('/admin/generate-examples-seed')
@admin_required
def generate_examples_seed():
    sql = db_generate_examples_seed()
    return Response(
        sql,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename="11-example-seed.sql"'}
    )


@bp.route('/admin/examples/<int:ex_id>/delete', methods=['POST'])
@admin_required
def admin_delete_example(ex_id):
    try:
        db_delete_example(ex_id)
        flash(_('Example deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_examples.admin_examples'))
