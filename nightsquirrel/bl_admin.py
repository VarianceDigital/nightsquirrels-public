import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, current_app
from flask_babel import gettext as _
from flask_login import login_required
from .auth import admin_required
from .db_admin import (db_admin_list_questions, db_admin_list_tutors, db_admin_list_users,
                        db_admin_update_user_flags, db_admin_list_payments, db_admin_retry_payment,
                        db_admin_stats, db_generate_library_seed, db_get_all_ref_image_keys)
from .s3_operations import list_s3_objects, batch_delete_s3_objects

_REF_IMAGES_BUCKET_NAME = os.environ.get('AWS_REF_IMAGES_BUCKET_NAME', 'nightsquirrel-reference-images')
from .payment import attempt_payment_for_ticket
from .db_ticket import db_admin_assign_tutor_to_ticket, db_admin_set_manual_quote
from .notifications import notify_tutor_assigned, notify_student_quote_ready

bp = Blueprint('bl_admin', __name__, url_prefix='/admin')


@bp.route('/')
@admin_required
def dashboard():
    stats = db_admin_stats()
    return render_template('admin/dashboard.html', mc={'admin': 'active'}, stats=stats)


@bp.route('/users')
@admin_required
def users():
    q = (request.args.get('q') or '').strip()
    rows = db_admin_list_users(q=q)
    return render_template('admin/users.html', mc={'admin': 'active'}, rows=rows, q=q)


@bp.post('/users/<int:usr_id>/flags')
@admin_required
def update_user_flags(usr_id: int):
    usr_isvalid = 'usr_isvalid' in request.form
    usr_is_student = 'usr_is_student' in request.form
    usr_is_tutor = 'usr_is_tutor' in request.form
    usr_is_admin = 'usr_is_admin' in request.form
    usr_is_payer = 'usr_is_payer' in request.form

    ok = db_admin_update_user_flags(usr_id, usr_isvalid, usr_is_student,
                                     usr_is_tutor, usr_is_admin, usr_is_payer)
    if ok:
        flash(_("User #%(id)s updated.", id=usr_id), "success")
    else:
        flash(_("User not found."), "danger")

    q = request.args.get('q') or ''
    return redirect(url_for('bl_admin.users', q=q))


@bp.route('/questions')
@admin_required
def questions():
    # filters (optional, but useful right away)
    q = (request.args.get('q') or '').strip()
    state = request.args.get('state')  # can be None / '' / '0' etc.
    assigned = request.args.get('assigned')  # '1' | '0' | None

    rows = db_admin_list_questions(q=q, state=state, assigned=assigned)
    tutors = db_admin_list_tutors()

    return render_template(
        'admin/questions.html',
        mc={'admin': 'active'},
        rows=rows,
        tutors=tutors,
        q=q,
        state=state,
        assigned=assigned
    )


@bp.post('/tickets/<int:tkt_id>/quote')
@admin_required
def set_manual_quote(tkt_id: int):
    raw_eur = (request.form.get('quote_eur') or '').strip()
    quote_note = (request.form.get('quote_note') or '').strip() or None

    try:
        quote_eur = float(raw_eur.replace(',', '.'))
        if quote_eur <= 0:
            raise ValueError
        quote_cents = int(round(quote_eur * 100))
    except (ValueError, TypeError):
        flash(_("Enter a valid price (e.g. 7.50)."), "warning")
        return redirect(url_for('bl_admin.questions', state='2'))

    ok = db_admin_set_manual_quote(tkt_id=tkt_id, quote_cents=quote_cents, quote_note=quote_note)
    if ok:
        notify_student_quote_ready(tkt_id)
        flash(_("Manual quote set: %(amount)s EUR.", amount=f"{quote_eur:.2f}"), "success")
    else:
        flash(_("Could not set quote (ticket not in review state?)."), "danger")
    return redirect(url_for('bl_admin.questions', state='2'))


@bp.post('/tickets/<int:tkt_id>/assign')
@admin_required
def assign_ticket(tkt_id: int):
    tutor_usr_id = request.form.get('tutor_usr_id') or None
    if tutor_usr_id == '':
        tutor_usr_id = None

    ok = db_admin_assign_tutor_to_ticket(tkt_id=tkt_id, tutor_usr_id=tutor_usr_id)
    if ok:
        if tutor_usr_id:
            notify_tutor_assigned(tkt_id)
        flash(_("Tutor assigned."), "success")
    else:
        flash(_("Assignment failed."), "danger")

    return redirect(url_for('bl_admin.questions'))


@bp.route('/payments')
@admin_required
def payments():
    status = (request.args.get('status') or '').strip() or None
    rows = db_admin_list_payments(status=status)
    return render_template('admin/payments.html', mc={'admin': 'active'},
                           rows=rows, status=status)


@bp.get('/purge-ref-images')
@admin_required
def purge_ref_images_preview():
    known  = db_get_all_ref_image_keys()
    all_keys = list_s3_objects(_REF_IMAGES_BUCKET_NAME)
    orphans  = sorted(k for k in all_keys if k not in known)
    return render_template('admin/purge_ref_images.html',
                           mc={'admin': 'active'},
                           orphans=orphans,
                           total_s3=len(all_keys),
                           known_count=len(known))


@bp.post('/purge-ref-images')
@admin_required
def purge_ref_images():
    known    = db_get_all_ref_image_keys()
    all_keys = list_s3_objects(_REF_IMAGES_BUCKET_NAME)
    orphans  = [k for k in all_keys if k not in known]
    deleted  = batch_delete_s3_objects(orphans, _REF_IMAGES_BUCKET_NAME)
    flash(_(f'Deleted %(n)s orphaned image(s) from S3.', n=deleted), 'success')
    return redirect(url_for('bl_admin.dashboard'))


@bp.get('/generate-library-seed')
@admin_required
def generate_library_seed():
    sql = db_generate_library_seed()
    return Response(
        sql,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename="9-library-seed.sql"'}
    )


@bp.get('/rebase')
@admin_required
def rebase_utilities():
    return render_template('admin/rebase.html', mc={'admin': 'active'})


@bp.get('/seed-sql')
@admin_required
def seed_sql():
    scripts_dir = os.path.normpath(os.path.join(current_app.root_path, '..', 'database scripts'))
    try:
        files = sorted(
            [f for f in os.listdir(scripts_dir) if f.endswith('.sql')],
            key=lambda f: int(f.split('-')[0])
        )
    except FileNotFoundError:
        return Response('-- database scripts folder not found', mimetype='text/plain', status=500)

    chunks = []
    for filename in files:
        with open(os.path.join(scripts_dir, filename), 'r', encoding='utf-8') as fh:
            content = fh.read()
        chunks.append(f'-- {"=" * 60}\n-- {filename}\n-- {"=" * 60}\n\n{content}\n')

    return Response(
        '\n'.join(chunks),
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename="nightsquirrel_seed.sql"'}
    )


@bp.post('/payments/<int:pay_id>/retry')
@admin_required
def retry_payment(pay_id: int):
    tkt_id = db_admin_retry_payment(pay_id)
    if tkt_id is None:
        flash(_("Payment not found or not in failed state."), "warning")
    else:
        paid = attempt_payment_for_ticket(tkt_id)
        if paid:
            flash(_("Payment #%(id)s retried successfully. Ticket delivered.", id=pay_id), "success")
        else:
            flash(_("Payment #%(id)s retry failed. Check error details.", id=pay_id), "danger")
    return redirect(url_for('bl_admin.payments', status='failed'))
