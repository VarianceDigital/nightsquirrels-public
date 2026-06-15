from flask import Blueprint, render_template, request, redirect, url_for, flash, g, Response
from flask_login import login_required
from flask_babel import gettext as _
from .auth import admin_required
from .db_interests import (
    db_list_interests, db_get_interest,
    db_create_interest, db_update_interest, db_delete_interest,
    db_list_interests_for_user, db_list_available_interests_for_user,
    db_attach_interest_to_user, db_detach_interest_from_user,
    db_generate_interests_seed,
)

bp = Blueprint('bl_interests', __name__, url_prefix='/interests')


# =============================================================================
# ADMIN — interest CRUD
# =============================================================================

@bp.route('/admin')
@admin_required
def admin_list():
    q = (request.args.get('q') or '').strip()
    interests = db_list_interests(q=q or None)
    return render_template('admin/interests/list.html',
                           mc={'admin': 'active'}, interests=interests, q=q)


@bp.route('/admin/new', methods=['GET', 'POST'])
@admin_required
def admin_new_interest():
    if request.method == 'POST':
        name_ita = (request.form.get('uit_name_ita') or '').strip()
        name_eng = (request.form.get('uit_name_eng') or '').strip()
        uit_type = (request.form.get('uit_type') or '').strip() or None

        if not name_ita or not name_eng:
            flash(_("Both Italian and English names are required."), "warning")
            return render_template('admin/interests/interest_form.html',
                                   mc={'admin': 'active'}, row=None,
                                   action=url_for('bl_interests.admin_new_interest'))
        try:
            db_create_interest(name_ita, name_eng, uit_type)
            flash(_("Interest created."), "success")
            return redirect(url_for('bl_interests.admin_list'))
        except Exception as e:
            if 'unique' in str(e).lower():
                flash(_("An interest with that name already exists."), "danger")
            else:
                flash(_("Database error: %(msg)s", msg=str(e)), "danger")

    return render_template('admin/interests/interest_form.html',
                           mc={'admin': 'active'}, row=None,
                           action=url_for('bl_interests.admin_new_interest'))


@bp.route('/admin/<int:uit_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_interest(uit_id: int):
    row = db_get_interest(uit_id)
    if row is None:
        flash(_("Interest not found."), "danger")
        return redirect(url_for('bl_interests.admin_list'))

    if request.method == 'POST':
        name_ita = (request.form.get('uit_name_ita') or '').strip()
        name_eng = (request.form.get('uit_name_eng') or '').strip()
        uit_type = (request.form.get('uit_type') or '').strip() or None

        if not name_ita or not name_eng:
            flash(_("Both Italian and English names are required."), "warning")
            return render_template('admin/interests/interest_form.html',
                                   mc={'admin': 'active'}, row=row,
                                   action=url_for('bl_interests.admin_edit_interest', uit_id=uit_id))
        try:
            db_update_interest(uit_id, name_ita, name_eng, uit_type)
            flash(_("Interest updated."), "success")
            return redirect(url_for('bl_interests.admin_list'))
        except Exception as e:
            if 'unique' in str(e).lower():
                flash(_("An interest with that name already exists."), "danger")
            else:
                flash(_("Database error: %(msg)s", msg=str(e)), "danger")

    return render_template('admin/interests/interest_form.html',
                           mc={'admin': 'active'}, row=row,
                           action=url_for('bl_interests.admin_edit_interest', uit_id=uit_id))


@bp.post('/admin/<int:uit_id>/delete')
@admin_required
def admin_delete_interest(uit_id: int):
    try:
        ok = db_delete_interest(uit_id)
        if ok:
            flash(_("Interest deleted."), "success")
        else:
            flash(_("Interest not found."), "danger")
    except Exception as e:
        flash(_("Database error: %(msg)s", msg=str(e)), "danger")
    return redirect(url_for('bl_interests.admin_list'))


# =============================================================================
# USER — own interests
# =============================================================================

@bp.post('/user/attach')
@login_required
def user_attach():
    uit_id_str = request.form.get('uit_id', '')
    try:
        uit_id = int(uit_id_str)
    except (TypeError, ValueError):
        flash(_("Invalid interest."), "warning")
        return redirect(url_for('bl_auth.userprofile'))
    try:
        db_attach_interest_to_user(uit_id, g.user_id)
    except Exception as e:
        flash(_("Error: %(msg)s", msg=str(e)), "danger")
    return redirect(url_for('bl_auth.userprofile') + '#interests')


@bp.post('/user/detach/<int:uit_id>')
@login_required
def user_detach(uit_id: int):
    try:
        db_detach_interest_from_user(uit_id, g.user_id)
    except Exception as e:
        flash(_("Error: %(msg)s", msg=str(e)), "danger")
    return redirect(url_for('bl_auth.userprofile') + '#interests')


# =============================================================================
# ADMIN — per-user interests
# =============================================================================

@bp.route('/admin/user/<int:usr_id>', methods=['GET', 'POST'])
@admin_required
def admin_user_interests(usr_id: int):
    if request.method == 'POST':
        action = request.form.get('action')
        uit_id_str = request.form.get('uit_id', '')
        try:
            uit_id = int(uit_id_str)
        except (TypeError, ValueError):
            flash(_("Invalid interest."), "warning")
            return redirect(url_for('bl_interests.admin_user_interests', usr_id=usr_id))
        try:
            if action == 'attach':
                db_attach_interest_to_user(uit_id, usr_id)
                flash(_("Interest added."), "success")
            elif action == 'detach':
                db_detach_interest_from_user(uit_id, usr_id)
                flash(_("Interest removed."), "success")
        except Exception as e:
            flash(_("Database error: %(msg)s", msg=str(e)), "danger")
        return redirect(url_for('bl_interests.admin_user_interests', usr_id=usr_id))

    from .db_auth import db_get_user_by_id
    user_row = db_get_user_by_id(usr_id)
    if user_row is None:
        flash(_("User not found."), "danger")
        return redirect(url_for('bl_admin.users'))
    attached = db_list_interests_for_user(usr_id)
    available = db_list_available_interests_for_user(usr_id)
    return render_template('admin/interests/user_interests.html',
                           mc={'admin': 'active'},
                           user_row=user_row, usr_id=usr_id,
                           attached=attached, available=available)


# =============================================================================
# ADMIN — seed download
# =============================================================================

@bp.get('/admin/generate-seed')
@admin_required
def generate_interests_seed():
    sql = db_generate_interests_seed()
    return Response(
        sql,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename="15-interests-seed.sql"'}
    )
