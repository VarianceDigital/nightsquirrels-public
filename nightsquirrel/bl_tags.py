# nightsquirrel/bl_tags.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from flask_login import login_required
from flask_babel import gettext as _
from .auth import admin_required
from .db_tags import (
    db_list_tags, db_get_tag,
    db_create_tag, db_update_tag, db_delete_tag,
    db_list_tags_for_question, db_attach_tag_to_question, db_detach_tag_from_question,
    db_question_for_tags,
    db_list_tags_for_reference, db_attach_tag_to_reference, db_detach_tag_from_reference,
    db_reference_for_tags,
)

bp = Blueprint('bl_tags', __name__, url_prefix='/tags')


# =============================================================================
# ADMIN — tag CRUD
# =============================================================================

@bp.route('/admin')
@admin_required
def admin_list():
    q = (request.args.get('q') or '').strip()
    tags = db_list_tags(q=q or None)
    return render_template('admin/tags/list.html',
                           mc={'admin': 'active'}, tags=tags, q=q)


@bp.route('/admin/new', methods=['GET', 'POST'])
@admin_required
def admin_new_tag():
    attach_ref = request.args.get('attach_ref', type=int)
    attach_qtn = request.args.get('attach_qtn', type=int)

    if request.method == 'POST':
        attach_ref = request.form.get('attach_ref', type=int)
        attach_qtn = request.form.get('attach_qtn', type=int)
        name_ita = (request.form.get('tag_name_ita') or '').strip()
        name_eng = (request.form.get('tag_name_eng') or '').strip()
        tag_type = (request.form.get('tag_type') or '').strip() or None
        tag_icon = (request.form.get('tag_icon') or '').strip() or None

        if not name_ita or not name_eng:
            flash(_("Both Italian and English names are required."), "warning")
            return render_template('admin/tags/tag_form.html',
                                   mc={'admin': 'active'}, row=None,
                                   action=url_for('bl_tags.admin_new_tag'),
                                   attach_ref=attach_ref, attach_qtn=attach_qtn)
        try:
            tag_id = db_create_tag(name_ita, name_eng, tag_type, tag_icon)
            flash(_("Tag created."), "success")
            if attach_ref:
                db_attach_tag_to_reference(tag_id, attach_ref)
                return redirect(url_for('bl_tags.manage_reference_tags', ref_id=attach_ref))
            if attach_qtn:
                db_attach_tag_to_question(tag_id, attach_qtn)
                return redirect(url_for('bl_tags.manage_question_tags', qtn_id=attach_qtn))
            return redirect(url_for('bl_tags.admin_list'))
        except Exception as e:
            msg = str(e)
            if 'unique' in msg.lower():
                flash(_("A tag with that name already exists."), "danger")
            else:
                flash(_("Database error: %(msg)s", msg=msg), "danger")

    return render_template('admin/tags/tag_form.html',
                           mc={'admin': 'active'}, row=None,
                           action=url_for('bl_tags.admin_new_tag'),
                           attach_ref=attach_ref, attach_qtn=attach_qtn)


@bp.route('/admin/<int:tag_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_tag(tag_id: int):
    row = db_get_tag(tag_id)
    if row is None:
        flash(_("Tag not found."), "danger")
        return redirect(url_for('bl_tags.admin_list'))

    if request.method == 'POST':
        name_ita = (request.form.get('tag_name_ita') or '').strip()
        name_eng = (request.form.get('tag_name_eng') or '').strip()
        tag_type = (request.form.get('tag_type') or '').strip() or None
        tag_icon = (request.form.get('tag_icon') or '').strip() or None

        if not name_ita or not name_eng:
            flash(_("Both Italian and English names are required."), "warning")
            return render_template('admin/tags/tag_form.html',
                                   mc={'admin': 'active'}, row=row,
                                   action=url_for('bl_tags.admin_edit_tag', tag_id=tag_id))
        try:
            db_update_tag(tag_id, name_ita, name_eng, tag_type, tag_icon)
            flash(_("Tag updated."), "success")
            return redirect(url_for('bl_tags.admin_list'))
        except Exception as e:
            msg = str(e)
            if 'unique' in msg.lower():
                flash(_("A tag with that name already exists."), "danger")
            else:
                flash(_("Database error: %(msg)s", msg=msg), "danger")

    return render_template('admin/tags/tag_form.html',
                           mc={'admin': 'active'}, row=row,
                           action=url_for('bl_tags.admin_edit_tag', tag_id=tag_id))


@bp.post('/admin/<int:tag_id>/delete')
@admin_required
def admin_delete_tag(tag_id: int):
    try:
        ok = db_delete_tag(tag_id)
        if ok:
            flash(_("Tag deleted."), "success")
        else:
            flash(_("Tag not found."), "danger")
    except Exception as e:
        flash(_("Database error: %(msg)s", msg=str(e)), "danger")
    return redirect(url_for('bl_tags.admin_list'))


# =============================================================================
# QUESTION TAGS
# =============================================================================

def _get_question_or_403(qtn_id: int):
    usr_id = None if g.usr_is_admin else g.user_id
    qrow = db_question_for_tags(qtn_id, usr_id)
    if not qrow:
        abort(403)
    return qrow


@bp.route('/question/<int:qtn_id>')
@login_required
def manage_question_tags(qtn_id: int):
    qrow = _get_question_or_403(qtn_id)
    attached = db_list_tags_for_question(qtn_id)
    attached_ids = {t['tag_id'] for t in attached}
    available = [t for t in db_list_tags() if t['tag_id'] not in attached_ids]
    return render_template('tags/manage_question_tags.html',
                           mc={}, qrow=qrow, attached=attached, available=available,
                           qtn_id=qtn_id)


@bp.post('/question/<int:qtn_id>/attach/<int:tag_id>')
@login_required
def attach_question_tag(qtn_id: int, tag_id: int):
    _get_question_or_403(qtn_id)
    db_attach_tag_to_question(tag_id, qtn_id)
    return redirect(url_for('bl_tags.manage_question_tags', qtn_id=qtn_id))


@bp.post('/question/<int:qtn_id>/detach/<int:tag_id>')
@login_required
def detach_question_tag(qtn_id: int, tag_id: int):
    _get_question_or_403(qtn_id)
    db_detach_tag_from_question(tag_id, qtn_id)
    return redirect(url_for('bl_tags.manage_question_tags', qtn_id=qtn_id))


# =============================================================================
# REFERENCE TAGS
# =============================================================================

def _get_reference_or_403(ref_id: int):
    usr_id = None if g.usr_is_admin else g.user_id
    rrow = db_reference_for_tags(ref_id, usr_id)
    if not rrow:
        abort(403)
    return rrow


@bp.route('/reference/<int:ref_id>')
@login_required
def manage_reference_tags(ref_id: int):
    rrow = _get_reference_or_403(ref_id)
    attached = db_list_tags_for_reference(ref_id)
    attached_ids = {t['tag_id'] for t in attached}
    available = [t for t in db_list_tags() if t['tag_id'] not in attached_ids]
    back_url = url_for('bl_references.admin_list') if g.usr_is_admin \
               else url_for('bl_references.my_refs')
    return render_template('tags/manage_reference_tags.html',
                           mc={}, rrow=rrow, attached=attached, available=available,
                           ref_id=ref_id, back_url=back_url)


@bp.post('/reference/<int:ref_id>/attach/<int:tag_id>')
@login_required
def attach_reference_tag(ref_id: int, tag_id: int):
    _get_reference_or_403(ref_id)
    db_attach_tag_to_reference(tag_id, ref_id)
    return redirect(url_for('bl_tags.manage_reference_tags', ref_id=ref_id))


@bp.post('/reference/<int:ref_id>/detach/<int:tag_id>')
@login_required
def detach_reference_tag(ref_id: int, tag_id: int):
    _get_reference_or_403(ref_id)
    db_detach_tag_from_reference(tag_id, ref_id)
    return redirect(url_for('bl_tags.manage_reference_tags', ref_id=ref_id))
