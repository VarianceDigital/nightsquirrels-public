# nightsquirrel/bl_tutor.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, g, abort, jsonify
from flask_babel import gettext as _
from .auth import manage_cookie_policy, tutor_required
from .layoutUtils import set_menu
from .db_ticket import (
    db_list_open_tickets, db_list_my_tickets,
    db_claim_ticket, db_unclaim_ticket, db_set_ticket_state,
    db_get_ticket_with_question_for_tutor,
    db_mark_ticket_and_answer_delivered,
)
from .db_answers import (
    db_create_answer_for_ticket,
    db_update_answer_complextext,
    db_get_answer_for_ticket,
)

from .states import *
from .notifications import notify_admin_payment_failed, notify_payer_payment_failed
from .db_comments import db_create_comment, db_list_comments_for_ticket
from .db_references import db_list_references_for_question, db_list_references_for_answer
from .db_tags import db_list_tags_for_question
from .payment import attempt_payment_for_ticket
from .pusher_client import get_pusher, get_pusher_key, get_pusher_cluster

bp = Blueprint('bl_tutor', __name__, url_prefix='/tutor')


@bp.route('/')
@tutor_required
@manage_cookie_policy
def tutor_dashboard():
    mc = set_menu("tutor")
    open_tickets = db_list_open_tickets()
    my_tickets = db_list_my_tickets(g.user_id)
    return render_template('tutor/dashboard.html', mc=mc, open_tickets=open_tickets, my_tickets=my_tickets)


@bp.post('/tickets/<int:tkt_id>/claim')
@tutor_required
@manage_cookie_policy
def ticket_claim(tkt_id):
    if not g.usr_isvalid:
        flash(_("Your account is suspended. You cannot claim tickets."), "danger")
        return redirect(url_for('bl_tutor.tutor_dashboard'))
    ok = db_claim_ticket(tkt_id, g.user_id)
    flash(_("Ticket claimed.") if ok else _("Could not claim ticket (maybe already taken)."))
    return redirect(url_for('bl_tutor.tutor_dashboard'))


@bp.post('/tickets/<int:tkt_id>/unclaim')
@tutor_required
@manage_cookie_policy
def ticket_unclaim(tkt_id):
    ok = db_unclaim_ticket(tkt_id, g.user_id)
    flash(_("Ticket released.") if ok else _("Could not release ticket."))
    return redirect(url_for('bl_tutor.tutor_dashboard'))


@bp.post('/tickets/<int:tkt_id>/in_progress')
@tutor_required
@manage_cookie_policy
def ticket_in_progress(tkt_id):
    if not g.usr_isvalid:
        flash(_("Your account is suspended."), "danger")
        return redirect(url_for('bl_tutor.tutor_dashboard'))
    ok = db_set_ticket_state(tkt_id, g.user_id, TKT_IN_PROGRESS)
    flash(_("Ticket set to in progress.") if ok else _("State change not allowed."))
    return redirect(url_for('bl_tutor.tutor_dashboard'))


@bp.post('/tickets/<int:tkt_id>/delivered')
@tutor_required
@manage_cookie_policy
def ticket_delivered(tkt_id):
    if not g.usr_isvalid:
        flash(_("Your account is suspended. You cannot deliver tickets."), "danger")
        return redirect(url_for('bl_tutor.tutor_dashboard'))
    ans = db_get_answer_for_ticket(tkt_id)
    if not ans:
        flash(_("Cannot deliver: no answer has been created yet."), "warning")
        return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))

    ok = db_mark_ticket_and_answer_delivered(tkt_id, g.user_id)
    if ok:
        paid = attempt_payment_for_ticket(tkt_id)
        if paid:
            flash(_("Ticket delivered and payment captured."), "success")
        else:
            notify_payer_payment_failed(tkt_id)
            notify_admin_payment_failed(tkt_id)
            flash(_("Ticket delivered but payment failed. Admin notified."), "warning")
    else:
        flash(_("Cannot deliver this ticket (not yours or wrong state)."), "warning")
    return redirect(url_for('bl_tutor.tutor_dashboard'))

@bp.route('/tickets/<int:tkt_id>')
@tutor_required
@manage_cookie_policy
def ticket_detail(tkt_id):
    mc = set_menu("")
    row = db_get_ticket_with_question_for_tutor(tkt_id)
    if not row:
        abort(404)

    is_assigned_to_me = (row.get("tutor_usr_id") == g.user_id)
    is_unassigned = (row.get("tutor_usr_id") is None)

    tkt_state = row.get("tkt_state", TKT_NEW)
    ans_id = row.get("ans_id") or row.get("a_ans_id")
    
    can_claim = is_unassigned and (tkt_state in CLAIMABLE_STATES)
    can_work  = is_assigned_to_me and (tkt_state in WORKABLE_STATES)

    has_answer = ans_id is not None
    can_create_answer = can_work and (not has_answer)
    can_edit_answer   = can_work and has_answer
    can_view_answer_ro = has_answer and (not can_edit_answer)

    comments = db_list_comments_for_ticket(tkt_id)
    question_refs = db_list_references_for_question(row['qtn_id'])
    answer_refs   = db_list_references_for_answer(ans_id) if ans_id else []
    question_tags = db_list_tags_for_question(row['qtn_id'])
    return render_template('tutor/ticket_detail.html', mc=mc, row=row,
                        can_claim=can_claim, can_create_answer=can_create_answer,
                        can_edit_answer=can_edit_answer,
                        can_view_answer_ro=can_view_answer_ro,
                        is_assigned_to_me=is_assigned_to_me,
                        has_answer=has_answer,
                        comments=comments,
                        question_refs=question_refs, answer_refs=answer_refs,
                        question_tags=question_tags,
                        pusher_key=get_pusher_key(),
                        pusher_cluster=get_pusher_cluster())


@bp.route('/tickets/<int:tkt_id>/answer', methods=('GET', 'POST'))
@tutor_required
@manage_cookie_policy
def answer_edit(tkt_id):
    mc = set_menu("")
    row = db_get_ticket_with_question_for_tutor(tkt_id)
    if not row:
        abort(404)

    # HARD SECURITY: must be assigned to me, and answer must exist
    if row.get("tutor_usr_id") != g.user_id:
        abort(403)
    if row.get("ans_id") is None:
        flash(_("No answer exists yet. Create one first."), "info")
        return redirect(url_for("bl_tutor.answer_create", tkt_id=tkt_id))

    if request.method == 'POST':
        ctx_delta = request.form.get('ctx_delta') or '{"ops":[]}'
        ctx_plaintext = (request.form.get('ctx_plaintext') or '').strip()
        deliver = ('btn_deliver' in request.form)

        if deliver and not ctx_plaintext:
            flash(_("Cannot deliver an empty answer."), "danger")
            return redirect(url_for('bl_tutor.answer_edit', tkt_id=tkt_id))

        ok = db_update_answer_complextext(
            tkt_id=tkt_id,
            tutor_usr_id=g.user_id,
            ctx_delta_json=ctx_delta,
            ctx_plaintext=ctx_plaintext
        )

        if ok:
            if deliver:
                if not g.usr_isvalid:
                    flash(_("Your account is suspended. You cannot deliver."), "danger")
                    return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))
                delivered = db_mark_ticket_and_answer_delivered(tkt_id=tkt_id, tutor_usr_id=g.user_id)
                if delivered:
                    paid = attempt_payment_for_ticket(tkt_id)
                    if paid:
                        flash(_("Answer delivered and payment captured."), "success")
                    else:
                        notify_payer_payment_failed(tkt_id)
                        notify_admin_payment_failed(tkt_id)
                        flash(_("Answer delivered but payment failed. Admin notified."), "warning")
                else:
                    flash(_("Deliver failed (is the ticket assigned + answer created?)."), "danger")
                return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))
            flash(_("Answer saved."), "success")
            return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))
        else:
            flash(_("Could not save answer."), "danger")

    # refresh answer (so page shows latest)
    ans = db_get_answer_for_ticket(tkt_id)
    return render_template('tutor/answer_edit.html', mc=mc, ticket=row, ans=ans, mode="edit")


@bp.route('/tickets/<int:tkt_id>/answer/new', methods=('GET', 'POST'))
@tutor_required
@manage_cookie_policy
def answer_create(tkt_id):
    mc = set_menu("")
    row = db_get_ticket_with_question_for_tutor(tkt_id)
    if not row:
        abort(404)

    # HARD SECURITY: must be assigned to me, and no answer exists
    if row.get("tutor_usr_id") != g.user_id:
        abort(403)
    if row.get("ans_id") is not None:
        flash(_("Answer already exists. Editing it instead."), "info")
        return redirect(url_for("bl_tutor.answer_edit", tkt_id=tkt_id))

    if request.method == "POST":
        ctx_delta = request.form.get("ctx_delta") or '{"ops":[]}'
        ctx_plaintext = (request.form.get("ctx_plaintext") or "").strip()
        deliver = ('btn_deliver' in request.form)
        ans_id = db_create_answer_for_ticket(
            tkt_id=tkt_id,
            tutor_usr_id=g.user_id,
            ctx_delta_json=ctx_delta,
            ctx_plaintext=ctx_plaintext,
        )

        if deliver:
            if not g.usr_isvalid:
                flash(_("Your account is suspended. You cannot deliver."), "danger")
                return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))
            delivered = db_mark_ticket_and_answer_delivered(tkt_id=tkt_id, tutor_usr_id=g.user_id)
            if delivered:
                paid = attempt_payment_for_ticket(tkt_id)
                if paid:
                    flash(_("Answer created and delivered. Payment captured."), "success")
                else:
                    notify_payer_payment_failed(tkt_id)
                    notify_admin_payment_failed(tkt_id)
                    flash(_("Answer delivered but payment failed. Admin notified."), "warning")
            else:
                flash(_("Deliver failed (is the ticket assigned + answer created?)."), "danger")
            return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))

        flash(_("Answer created (#%(id)s).", id=ans_id), "success")
        return redirect(url_for("bl_tutor.ticket_detail", tkt_id=tkt_id))

    # GET: render empty editor (ans is None)
    return render_template("tutor/answer_edit.html", mc=mc, ticket=row, ans=None, mode="create")


@bp.post('/tickets/<int:tkt_id>/comment')
@tutor_required
@manage_cookie_policy
def add_comment_tutor(tkt_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    row = db_get_ticket_with_question_for_tutor(tkt_id)
    if not row:
        if is_ajax:
            return jsonify(ok=False, error=_("Ticket not found.")), 404
        abort(404)
    if row.get('tutor_usr_id') != g.user_id:
        if is_ajax:
            return jsonify(ok=False, error=_("Not your ticket.")), 403
        abort(403)

    ctx_delta = request.form.get('cmt_ctx_delta') or '{"ops":[]}'
    ctx_plaintext = (request.form.get('cmt_ctx_plaintext') or '').strip()
    if not ctx_plaintext:
        if is_ajax:
            return jsonify(ok=False, error=_("Cannot post an empty comment.")), 400
        flash(_("Cannot post an empty comment."), "warning")
        return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))

    try:
        cmt = db_create_comment(tkt_id, g.user_id, ctx_delta, ctx_plaintext)

        # Trigger Pusher event
        p = get_pusher()
        if p:
            try:
                p.trigger(f"private-ticket-{tkt_id}", 'new-comment', {
                    'cmt_id': cmt['cmt_id'],
                    'tkt_id': cmt['tkt_id'],
                    'usr_id': cmt['usr_id'],
                    'usr_name': g.user_name or g.user_email,
                    'cmt_ctx_delta_text': cmt['cmt_ctx_delta_text'],
                    'cmt_ctx_plaintext': cmt['cmt_ctx_plaintext'],
                    'cmt_created_at': cmt['cmt_created_at'].strftime('%Y-%m-%d %H:%M'),
                })
            except Exception:
                pass  # fail silently

        if is_ajax:
            return jsonify(
                ok=True,
                cmt_id=cmt['cmt_id'],
                usr_name=g.user_name or g.user_email,
                cmt_ctx_delta_text=cmt['cmt_ctx_delta_text'],
                cmt_ctx_plaintext=cmt['cmt_ctx_plaintext'],
                cmt_created_at=cmt['cmt_created_at'].strftime('%Y-%m-%d %H:%M'),
            )

        flash(_("Comment posted."), "success")
    except Exception as e:
        if is_ajax:
            return jsonify(ok=False, error=str(e)), 500
        flash(_("Error posting comment: %(error)s", error=str(e)), "danger")
    return redirect(url_for('bl_tutor.ticket_detail', tkt_id=tkt_id))
