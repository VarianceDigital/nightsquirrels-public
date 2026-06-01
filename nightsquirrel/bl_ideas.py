from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, g)
from flask_babel import gettext as _
from functools import wraps
import psycopg2, json

from .auth import login_required
from .db_ideas import (db_list_ideas, db_get_idea, db_create_idea,
                       db_update_idea, db_update_idea_body, db_delete_idea,
                       db_list_tags_for_idea, db_list_tags_available_for_idea,
                       db_attach_tag_to_idea, db_detach_tag_from_idea,
                       db_list_refs_for_idea, db_list_refs_available_for_idea,
                       db_attach_ref_to_idea, db_detach_ref_from_idea,
                       db_list_answers_for_idea, db_list_answers_available_for_idea,
                       db_attach_answer_to_idea, db_detach_answer_from_idea)

bp = Blueprint('bl_ideas', __name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _str(field: str):
    return (request.form.get(field) or '').strip() or None


def _parse_delta(field: str) -> dict:
    raw = request.form.get(field, '').strip()
    try:
        return json.loads(raw) if raw else {'ops': []}
    except (ValueError, TypeError):
        return {'ops': []}


def _is_admin():
    return bool(getattr(g, 'usr_is_admin', False))


def _is_tutor():
    return bool(getattr(g, 'usr_is_tutor', False))


def _current_user_id():
    return getattr(g, 'user_id', None)


def staff_required(view):
    """Allow access to admins and tutors."""
    @wraps(view)
    @login_required
    def wrapped(**kwargs):
        if not (_is_admin() or _is_tutor()):
            abort(403)
        return view(**kwargs)
    return wrapped


def _check_idea_access(idea):
    """Abort 403 if current user is neither admin nor the idea owner."""
    if not _is_admin() and idea['usr_id'] != _current_user_id():
        abort(403)


# ── admin/tutor CRUD ──────────────────────────────────────────────────────────

@bp.route('/admin/ideas')
@staff_required
def admin_ideas():
    if _is_admin():
        ideas = db_list_ideas()
    else:
        ideas = db_list_ideas(usr_id=_current_user_id())
    return render_template('admin/ideas/list.html',
                           mc={'admin': 'active'}, ideas=ideas)


@bp.route('/admin/ideas/new', methods=['GET', 'POST'])
@staff_required
def admin_new_idea():
    if request.method == 'POST':
        title = _str('idea_title')
        if not title:
            flash(_('Title is required.'), 'danger')
            return render_template('admin/ideas/form.html',
                                   mc={'admin': 'active'}, row=None,
                                   action=url_for('bl_ideas.admin_new_idea'))
        try:
            idea_id = db_create_idea(
                title     = title,
                subtitle  = _str('idea_subtitle'),
                lang      = request.form.get('idea_lang', 'it'),
                usr_id    = _current_user_id(),
                published = 'idea_is_published' in request.form,
            )
            flash(_('Idea created.'), 'success')
            return redirect(url_for('bl_ideas.admin_edit_idea', idea_id=idea_id))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/ideas/form.html',
                           mc={'admin': 'active'}, row=None,
                           action=url_for('bl_ideas.admin_new_idea'))


@bp.route('/admin/ideas/<int:idea_id>/edit', methods=['GET', 'POST'])
@staff_required
def admin_edit_idea(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    if request.method == 'POST':
        title = _str('idea_title')
        if not title:
            flash(_('Title is required.'), 'danger')
        else:
            try:
                db_update_idea(
                    idea_id   = idea_id,
                    title     = title,
                    subtitle  = _str('idea_subtitle'),
                    lang      = request.form.get('idea_lang', 'it'),
                    published = 'idea_is_published' in request.form,
                )
                flash(_('Idea updated.'), 'success')
                return redirect(url_for('bl_ideas.admin_ideas'))
            except psycopg2.Error as e:
                flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/ideas/form.html',
                           mc={'admin': 'active'}, row=row,
                           action=url_for('bl_ideas.admin_edit_idea',
                                         idea_id=idea_id))


@bp.route('/admin/ideas/<int:idea_id>/whiteboard', methods=['GET', 'POST'])
@staff_required
def admin_idea_whiteboard(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    if request.method == 'POST':
        try:
            db_update_idea_body(idea_id, _parse_delta('idea_body_delta'))
            flash(_('Whiteboard saved.'), 'success')
            return redirect(url_for('bl_ideas.admin_idea_whiteboard',
                                    idea_id=idea_id))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/ideas/whiteboard.html',
                           mc={'admin': 'active'}, row=row)


@bp.route('/admin/ideas/<int:idea_id>/delete', methods=['POST'])
@staff_required
def admin_delete_idea(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    try:
        db_delete_idea(idea_id)
        flash(_('Idea deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_ideas.admin_ideas'))


# ── Tag management ────────────────────────────────────────────────────────────

@bp.route('/admin/ideas/<int:idea_id>/tags')
@staff_required
def admin_idea_tags(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    attached  = db_list_tags_for_idea(idea_id)
    available = db_list_tags_available_for_idea(idea_id)
    return render_template('admin/ideas/manage_tags.html',
                           mc={'admin': 'active'}, row=row,
                           attached=attached, available=available)


@bp.post('/admin/ideas/<int:idea_id>/tags/attach/<int:tag_id>')
@staff_required
def admin_idea_attach_tag(idea_id, tag_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_attach_tag_to_idea(idea_id, tag_id)
    return redirect(url_for('bl_ideas.admin_idea_tags', idea_id=idea_id))


@bp.post('/admin/ideas/<int:idea_id>/tags/detach/<int:tag_id>')
@staff_required
def admin_idea_detach_tag(idea_id, tag_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_detach_tag_from_idea(idea_id, tag_id)
    return redirect(url_for('bl_ideas.admin_idea_tags', idea_id=idea_id))


# ── Reference management ──────────────────────────────────────────────────────

@bp.route('/admin/ideas/<int:idea_id>/references')
@staff_required
def admin_idea_refs(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    attached  = db_list_refs_for_idea(idea_id)
    available = db_list_refs_available_for_idea(idea_id)
    return render_template('admin/ideas/manage_refs.html',
                           mc={'admin': 'active'}, row=row,
                           attached=attached, available=available)


@bp.post('/admin/ideas/<int:idea_id>/references/attach/<int:ref_id>')
@staff_required
def admin_idea_attach_ref(idea_id, ref_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_attach_ref_to_idea(idea_id, ref_id)
    return redirect(url_for('bl_ideas.admin_idea_refs', idea_id=idea_id))


@bp.post('/admin/ideas/<int:idea_id>/references/detach/<int:ref_id>')
@staff_required
def admin_idea_detach_ref(idea_id, ref_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_detach_ref_from_idea(idea_id, ref_id)
    return redirect(url_for('bl_ideas.admin_idea_refs', idea_id=idea_id))


# ── Answer management ─────────────────────────────────────────────────────────

@bp.route('/admin/ideas/<int:idea_id>/answers')
@staff_required
def admin_idea_answers(idea_id):
    row = db_get_idea(idea_id)
    if not row:
        flash(_('Idea not found.'), 'danger')
        return redirect(url_for('bl_ideas.admin_ideas'))
    _check_idea_access(row)
    attached  = db_list_answers_for_idea(idea_id)
    available = db_list_answers_available_for_idea(idea_id)
    return render_template('admin/ideas/manage_answers.html',
                           mc={'admin': 'active'}, row=row,
                           attached=attached, available=available)


@bp.post('/admin/ideas/<int:idea_id>/answers/attach/<int:ans_id>')
@staff_required
def admin_idea_attach_answer(idea_id, ans_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_attach_answer_to_idea(idea_id, ans_id)
    return redirect(url_for('bl_ideas.admin_idea_answers', idea_id=idea_id))


@bp.post('/admin/ideas/<int:idea_id>/answers/detach/<int:ans_id>')
@staff_required
def admin_idea_detach_answer(idea_id, ans_id):
    row = db_get_idea(idea_id)
    if not row:
        abort(404)
    _check_idea_access(row)
    db_detach_answer_from_idea(idea_id, ans_id)
    return redirect(url_for('bl_ideas.admin_idea_answers', idea_id=idea_id))
