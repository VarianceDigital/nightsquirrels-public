from flask import abort

import json
import logging
import os
import uuid

log = logging.getLogger(__name__)
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, request, flash, url_for, g, jsonify
from flask_login import login_required
from flask_babel import gettext as _

from .layoutUtils import set_menu, read_data_from_form
from .auth import manage_cookie_policy
from .db_lookup import db_get_subjects, db_get_questiontypes, db_get_schooltypes
from .db_questions import (db_create_question_with_ticket, db_list_questions_for_user,
                           db_get_question_detail, db_delete_question,
                           db_update_question_with_complextext,
                           db_soft_delete_question)
from .db_ticket import db_apply_quote_to_ticket, db_accept_quote, db_reject_quote, db_close_ticket, db_set_needs_clarification
from .db_payment import db_student_has_active_payer, db_get_active_payer_link, db_create_payment_record, db_get_default_payment_method
from .db_documents import db_create_document, db_get_documents_for_question, db_delete_document, db_save_extracted_delta
from .db_references import (db_list_references_for_question, db_list_references_for_answer,
                            db_get_reference, db_attach_reference_to_question)
from .db_tags import db_list_tags_for_question, db_tags_for_questions_batch, db_list_tags_for_reference, db_attach_tag_to_question
from .ai_provider import extract_image_to_delta
from .s3_operations import upload_document_to_s3, upload_bytes_to_s3, delete_file_from_s3
from .pricing import quote_from_question_data
from .notifications import (notify_payer_quote_accepted, notify_student_quote_ready,
                            notify_student_quote_accepted, notify_tutor_ticket_closed,
                            notify_tutor_question_deleted, notify_student_quote_rejected,
                            notify_student_ticket_closed, notify_student_needs_clarification)
from .states import (TKT_NEW, TKT_NEEDS_CLARIFICATION, TKT_QUOTED, TKT_NEEDS_REVIEW,
                     TKT_ASSIGNED, TKT_DELIVERED, TKT_DELIVERED_PENDING_PAYMENT,
                     QUESTION_EDITABLE_STATES)
from .question_analysis import analyze_and_gate_question
from .db_comments import db_create_comment, db_list_comments_for_ticket
from .pusher_client import get_pusher, get_pusher_key, get_pusher_cluster

ALLOWED_DOC_TYPES = {
    'image/jpeg', 'image/png', 'image/heic', 'application/pdf',
}
MAX_DOC_SIZE = 10 * 1024 * 1024  # 10 MB

bp = Blueprint('bl_question', __name__, url_prefix='/questions')


@bp.route('/upload-image', methods=('POST',))
@login_required
def upload_image():
    """Upload an image for inline embedding in a Quill editor. Returns {url: ...}.
    Accepts the JPEG blob produced by the client-side canvas resize."""
    img = request.files.get('image')
    if not img:
        return jsonify({'error': 'no image'}), 400
    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    if img.content_type not in allowed:
        return jsonify({'error': 'unsupported type'}), 400
    data = img.read()
    if len(data) > 5 * 1024 * 1024:
        return jsonify({'error': 'too large'}), 400
    ext = 'png' if img.content_type == 'image/png' else 'jpg'
    s3_key = f"editor-images/{uuid.uuid4().hex}.{ext}"
    upload_bytes_to_s3(data, s3_key, os.environ['AWS_DOCS_BUCKET_NAME'], img.content_type)
    return jsonify({'url': f"{os.environ['AWS_DOCS_BUCKET_URL']}{s3_key}"})


@bp.route('/extract-image', methods=('POST',))
@login_required
def extract_image_endpoint():
    """Accept a cropped image blob and return AI-extracted Quill delta + confidence."""
    doc_file = request.files.get('image')
    if not doc_file:
        return jsonify({'error': 'no image'}), 400
    if not doc_file.content_type.startswith('image/') or \
            doc_file.content_type in ('image/heic', 'image/heif'):
        return jsonify({'error': 'unsupported type'}), 400
    result = extract_image_to_delta(doc_file.read(), doc_file.content_type)
    if result is None:
        return jsonify({'error': 'extraction failed'}), 500
    return jsonify(result)


@bp.route('/', methods=('GET',))
@login_required
@manage_cookie_policy
def my_questions():
    mc = set_menu("questions")
    rows = db_list_questions_for_user(g.user_id)
    tags_by_qtn = db_tags_for_questions_batch([r['qtn_id'] for r in rows])
    return render_template('question/my_questions.html', mc=mc, rows=rows,
                           tags_by_qtn=tags_by_qtn)


@bp.route('/new', methods=('GET', 'POST'))
@login_required
@manage_cookie_policy
def new_question():
    mc = set_menu("questions")
    subjects = db_get_subjects()
    qtypes = db_get_questiontypes()
    schooltypes = db_get_schooltypes()

    if request.method == 'POST':
        if not g.usr_isvalid:
            flash(_("Your account is suspended. You cannot create questions."), "danger")
            return redirect(url_for('bl_question.my_questions'))
        form = read_data_from_form()

        title = (form.get('qtn_title') or '').strip()
        if not title:
            flash(_("Title is required."), "warning")
            return render_template('question/new_question.html', mc=mc,
                                   subjects=subjects, qtypes=qtypes, schooltypes=schooltypes,
                                   form=form)

        # Quill hidden fields
        ctx_delta = form.get('ctx_delta') or '{"ops":[]}'
        ctx_plaintext = (form.get('ctx_plaintext') or '').strip()

        # Metadata (optional, but we collect now)
        def to_int(v):
            if v is None:
                return None
            try:
                return int(v)
            except Exception:
                return None

        sbj_id = to_int(form.get('sbj_id'))
        qtp_id = to_int(form.get('qtp_id'))
        sct_id = to_int(form.get('sct_id'))
        difficulty = to_int(form.get('qtn_difficulty'))
        grade = to_int(form.get('qtn_grade'))
        notes = form.get('qtn_notes')

        try:
            ids = db_create_question_with_ticket(
                usr_id=g.user_id,
                title=title,
                sbj_id=sbj_id,
                qtp_id=qtp_id,
                sct_id=sct_id,
                difficulty=difficulty,
                grade=grade,
                notes=notes,
                ctx_delta_json=ctx_delta,
                ctx_plaintext=ctx_plaintext
            )
            # --- document upload (before AI gate so it's always saved) ---
            doc_file = request.files.get('document')
            if doc_file and doc_file.filename:
                if doc_file.content_type not in ALLOWED_DOC_TYPES:
                    flash(_("Invalid file type. Allowed: JPG, PNG, HEIC, PDF."), "warning")
                else:
                    doc_file.seek(0, 2)
                    size_bytes = doc_file.tell()
                    doc_file.seek(0)
                    if size_bytes > MAX_DOC_SIZE:
                        flash(_("File too large. Max 10 MB."), "warning")
                    else:
                        safe_name = secure_filename(doc_file.filename)
                        s3_key = f"documents/{ids['qtn_id']}/{uuid.uuid4().hex}_{safe_name}"
                        upload_document_to_s3(
                            doc_file, s3_key,
                            os.environ['AWS_DOCS_BUCKET_NAME'],
                            doc_file.content_type
                        )
                        doc_id = db_create_document(
                            qtn_id=ids['qtn_id'],
                            filename=safe_name,
                            s3_key=s3_key,
                            content_type=doc_file.content_type,
                            size_bytes=size_bytes,
                        )
                        if doc_file.content_type.startswith('image/') and \
                                doc_file.content_type not in ('image/heic', 'image/heif'):
                            try:
                                doc_file.seek(0)
                                extracted = extract_image_to_delta(doc_file.read(), doc_file.content_type)
                                if extracted:
                                    db_save_extracted_delta(doc_id, json.dumps(extracted['delta']))
                                    if not ctx_plaintext:
                                        ctx_plaintext = extracted.get('plaintext', '')
                            except Exception:
                                log.warning("Background image extraction failed for doc %s", doc_id, exc_info=True)

            # --- AI suitability gate ---
            is_quotable, student_hint, predictions = analyze_and_gate_question(
                tkt_id=ids['tkt_id'], qtn_id=ids['qtn_id'],
                title=title, plaintext=ctx_plaintext,
                ctx_delta_json=ctx_delta,
                sbj_id=sbj_id, qtp_id=qtp_id, sct_id=sct_id,
                grade=grade, difficulty=difficulty,
            )
            if not is_quotable:
                db_set_needs_clarification(ids['tkt_id'], student_hint)
                notify_student_needs_clarification(ids['tkt_id'], student_hint)
                flash(_("Please review the feedback and update your question."), "warning")
                return redirect(url_for('bl_question.question_detail', qtn_id=ids['qtn_id']))

            # Use AI predictions for quoting if available
            q_sbj_id = predictions['sbj_id'] if predictions else sbj_id
            q_sct_id = predictions['sct_id'] if predictions else sct_id
            q_grade = predictions['grade'] if predictions else grade
            q_difficulty = predictions['difficulty'] if predictions else difficulty

            # --- auto-quote the ticket ---
            quote = quote_from_question_data(
                sbj_id=q_sbj_id,
                qtp_id=qtp_id,
                sct_id=q_sct_id,
                grade=q_grade,
                difficulty=q_difficulty,
                plaintext=ctx_plaintext,
            )
            if quote["overflow"]:
                new_state = TKT_NEEDS_REVIEW
            else:
                new_state = TKT_QUOTED

            db_apply_quote_to_ticket(
                tkt_id=ids['tkt_id'],
                quote_points=quote["points"],
                quote_version=quote["version"],
                quote_note=quote["note"],
                new_state=new_state,
                quote_payload=quote["quote_payload"],
                quote_signature=quote["quote_signature"],
                quote_input=quote["quote_input"],
            )

            if new_state == TKT_QUOTED:
                notify_student_quote_ready(ids['tkt_id'])

            # Attach source reference if question was started from a reference
            try:
                from_ref_id = int(form.get('from_ref') or 0) or None
            except (ValueError, TypeError):
                from_ref_id = None
            if from_ref_id:
                db_attach_reference_to_question(ref_id=from_ref_id, qtn_id=ids['qtn_id'])
                ref_tags_raw = db_list_tags_for_reference(from_ref_id)
                for i, tag in enumerate(ref_tags_raw, start=1):
                    db_attach_tag_to_question(tag_id=tag['tag_id'], qtn_id=ids['qtn_id'], seqno=i)

            flash(_("Question submitted!"), "success")
            return redirect(url_for('bl_question.question_detail', qtn_id=ids['qtn_id']))
        except Exception as e:
            flash(_("Error while saving the question: %(error)s", error=str(e)), "danger")

    # Pre-fill from user's academic profile (new questions only)
    profile_defaults = {}
    if g.usr_is_student:
        if getattr(g, 'sct_id', None) is not None:
            profile_defaults['sct_id'] = str(g.sct_id)
        if getattr(g, 'usr_school_grade', None) is not None:
            profile_defaults['qtn_grade'] = str(g.usr_school_grade)

    # Pre-fill from a reference (from_ref + qtp_id query params)
    ref_context = None
    from_ref_id = request.args.get('from_ref', type=int)
    if from_ref_id:
        from_ref = db_get_reference(from_ref_id)
        if from_ref:
            ref_tags = db_list_tags_for_reference(from_ref_id)
            qtp_id_pre = request.args.get('qtp_id', type=int)
            qtype_name = next((t['qtp_name_ita'] for t in qtypes if t['qtp_id'] == qtp_id_pre), None)
            ref_title = from_ref.get('ref_title') or ''
            suggested_title = f"{qtype_name}: {ref_title}" if qtype_name else ref_title
            profile_defaults['qtn_title'] = suggested_title
            if qtp_id_pre:
                profile_defaults['qtp_id'] = str(qtp_id_pre)
            ref_context = {'ref_id': from_ref_id, 'ref': from_ref, 'tags': ref_tags}

    return render_template('question/new_question.html', mc=mc,
                           subjects=subjects, qtypes=qtypes, schooltypes=schooltypes,
                           form=profile_defaults, ref_context=ref_context)

@bp.route('/<int:qtn_id>', methods=('GET',))
@login_required
@manage_cookie_policy
def question_detail(qtn_id):
    mc = set_menu("questions")
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row:
        abort(404)
    has_payer = db_student_has_active_payer(g.user_id)
    has_vault = False
    if has_payer:
        payer_link = db_get_active_payer_link(g.user_id)
        if payer_link:
            pmt = db_get_default_payment_method(payer_link['payer_usr_id'])
            has_vault = bool(pmt and pmt.get('pmt_vault_status') == 'vaulted')
    documents = db_get_documents_for_question(qtn_id)
    s3docsurl = os.environ['AWS_DOCS_BUCKET_URL']
    comments = []
    if row['tkt_id'] and row.get('tkt_state', TKT_NEW) >= TKT_ASSIGNED:
        comments = db_list_comments_for_ticket(row['tkt_id'])
    question_refs = db_list_references_for_question(qtn_id)
    answer_refs   = db_list_references_for_answer(row['ans_id']) if row.get('ans_id') else []
    question_tags = db_list_tags_for_question(qtn_id)
    return render_template('question/question_detail.html', mc=mc, row=row,
                           has_payer=has_payer, has_vault=has_vault,
                           documents=documents, s3docsurl=s3docsurl,
                           comments=comments,
                           question_refs=question_refs,
                           answer_refs=answer_refs,
                           question_tags=question_tags,
                           pusher_key=get_pusher_key(),
                           pusher_cluster=get_pusher_cluster())

@bp.route('/<int:qtn_id>/delete', methods=('POST',))
@login_required
@manage_cookie_policy
def delete_question(qtn_id):
    mc = set_menu("questions")
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row:
        flash(_("Question not found (or not yours)."), "warning")
        return redirect(url_for('bl_question.my_questions'))

    try:
        tkt_state = row.get('tkt_state', TKT_NEW) or TKT_NEW

        if tkt_state >= TKT_DELIVERED_PENDING_PAYMENT:
            # Soft delete: preserve data for auditing
            ok = db_soft_delete_question(qtn_id, g.user_id)
            if ok:
                flash(_("Question archived."), "success")
            else:
                flash(_("Could not archive question."), "warning")
        else:
            # Hard delete: safe to remove
            tkt_id = row.get('tkt_id')
            tutor_id = row.get('tutor_usr_id')

            # Notify tutor before deleting if one was assigned
            if tkt_id and tutor_id and tkt_state >= TKT_ASSIGNED:
                notify_tutor_question_deleted(tkt_id)

            # Clean up S3 documents
            docs = db_get_documents_for_question(qtn_id)
            for doc in docs:
                delete_file_from_s3(doc['doc_s3_key'], os.environ['AWS_DOCS_BUCKET_NAME'])

            ok = db_delete_question(qtn_id, g.user_id)
            if ok:
                flash(_("Question deleted."), "success")
            else:
                flash(_("Question not found (or not yours)."), "warning")
    except Exception as e:
        flash(_("Delete failed: %(error)s", error=str(e)), "danger")

    return redirect(url_for('bl_question.my_questions'))

@bp.route('/<int:qtn_id>/accept', methods=('POST',))
@login_required
@manage_cookie_policy
def accept_quote(qtn_id):
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row or not row['tkt_id']:
        abort(404)

    if not g.usr_isvalid:
        flash(_("Your account is suspended. You cannot accept quotes."), "danger")
        return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

    # --- PAYER GATE: student must have a payer linked before accepting ---
    if not db_student_has_active_payer(g.user_id):
        flash(_("You must register a payer before accepting a quote."), "warning")
        return redirect(url_for('bl_payer.register_payer',
                                next=url_for('bl_question.question_detail', qtn_id=qtn_id)))

    # --- VAULT GATE: payer's PayPal must be vaulted before accepting ---
    payer_link = db_get_active_payer_link(g.user_id)
    pmt = db_get_default_payment_method(payer_link['payer_usr_id'])
    if not pmt or pmt.get('pmt_vault_status') != 'vaulted':
        flash(_("Your payer's PayPal is not connected yet. Payment must be set up before accepting."), "warning")
        return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

    # --- resolve selected option ---
    option_id = request.form.get('option_id')
    selected_cents = None

    if option_id and row.get('tkt_quote_payload'):
        payload = row['tkt_quote_payload']
        opts = {o['id']: o for o in (payload.get('options') or [])}
        if option_id not in opts:
            flash(_("Invalid option selected."), "warning")
            return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))
        selected_cents = opts[option_id]['price_cents']
        delivery_hours = opts[option_id].get('delivery_hours')
    else:
        # Fallback: extract price from payload single option
        payload = row.get('tkt_quote_payload') or {}
        opts = payload.get('options') or []
        if opts:
            selected_cents = opts[0]['price_cents']
            option_id = opts[0]['id']
            delivery_hours = opts[0].get('delivery_hours')
        else:
            flash(_("No quote options available."), "warning")
            return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

    ok = db_accept_quote(row['tkt_id'], g.user_id, option_id, selected_cents, delivery_hours)
    if ok:
        # Create a pending payment record and notify the payer
        payer_link = db_get_active_payer_link(g.user_id)
        if payer_link:
            db_create_payment_record(
                tkt_id=row['tkt_id'],
                payer_usr_id=payer_link['payer_usr_id'],
                amount_cents=selected_cents,
                currency=row['tkt_currency'],
            )
            notify_payer_quote_accepted(row['tkt_id'])

        notify_student_quote_accepted(row['tkt_id'])
        flash(_("Quote accepted. A tutor will work on your question."), "success")
    else:
        flash(_("Could not accept quote (wrong state or not yours)."), "warning")
    return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))


@bp.route('/<int:qtn_id>/reject', methods=('POST',))
@login_required
@manage_cookie_policy
def reject_quote(qtn_id):
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row or not row['tkt_id']:
        abort(404)
    ok = db_reject_quote(row['tkt_id'], g.user_id)
    if ok:
        notify_student_quote_rejected(row['tkt_id'])
        flash(_("Quote declined."), "info")
    else:
        flash(_("Could not decline quote (wrong state or not yours)."), "warning")
    return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))


@bp.route('/<int:qtn_id>/close', methods=('POST',))
@login_required
@manage_cookie_policy
def close_ticket(qtn_id):
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row or not row['tkt_id']:
        abort(404)
    ok = db_close_ticket(row['tkt_id'], g.user_id)
    if ok:
        notify_tutor_ticket_closed(row['tkt_id'])
        notify_student_ticket_closed(row['tkt_id'])
        flash(_("Delivery accepted. Ticket closed."), "success")
    else:
        flash(_("Could not close ticket (wrong state or not yours)."), "warning")
    return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))


@bp.route('/<int:qtn_id>/comments', methods=('POST',))
@login_required
@manage_cookie_policy
def add_comment_student(qtn_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    row = db_get_question_detail(qtn_id, g.user_id)
    if not row or not row['tkt_id']:
        if is_ajax:
            return jsonify(ok=False, error=_("Question not found.")), 404
        abort(404)
    if row.get('tkt_state', TKT_NEW) < TKT_ASSIGNED:
        if is_ajax:
            return jsonify(ok=False, error=_("Comments are not available for this ticket state.")), 403
        flash(_("Comments are not available for this ticket state."), "warning")
        return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

    ctx_delta = request.form.get('cmt_ctx_delta') or '{"ops":[]}'
    ctx_plaintext = (request.form.get('cmt_ctx_plaintext') or '').strip()
    if not ctx_plaintext:
        if is_ajax:
            return jsonify(ok=False, error=_("Cannot post an empty comment.")), 400
        flash(_("Cannot post an empty comment."), "warning")
        return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

    try:
        cmt = db_create_comment(row['tkt_id'], g.user_id, ctx_delta, ctx_plaintext)

        # Trigger Pusher event
        p = get_pusher()
        if p:
            try:
                p.trigger(f"private-ticket-{row['tkt_id']}", 'new-comment', {
                    'cmt_id': cmt['cmt_id'],
                    'tkt_id': cmt['tkt_id'],
                    'usr_id': cmt['usr_id'],
                    'usr_name': g.user_name or g.user_email,
                    'cmt_ctx_delta_text': cmt['cmt_ctx_delta_text'],
                    'cmt_ctx_plaintext': cmt['cmt_ctx_plaintext'],
                    'cmt_created_at': cmt['cmt_created_at'].strftime('%Y-%m-%d %H:%M'),
                })
            except Exception:
                pass  # fail silently, like notifications

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
    return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))


@bp.route('/<int:qtn_id>/edit', methods=('GET','POST'))
@login_required
@manage_cookie_policy
def question_edit(qtn_id):
    mc = set_menu("questions")
    row = db_get_question_detail(qtn_id, g.user_id)
    if not row:
        abort(404)

    subjects = db_get_subjects()
    qtypes = db_get_questiontypes()
    schooltypes = db_get_schooltypes()

    if request.method == 'POST':
        if row.get('tkt_state') not in QUESTION_EDITABLE_STATES:
            abort(403)
        if not g.usr_isvalid:
            flash(_("Your account is suspended. You cannot edit questions."), "danger")
            return redirect(url_for('bl_question.my_questions'))

        form = read_data_from_form()

        title = (form.get('qtn_title') or '').strip()
        if not title:
            flash(_("Title is required."), "warning")
            documents = db_get_documents_for_question(qtn_id)
            s3docsurl = os.environ['AWS_DOCS_BUCKET_URL']
            return render_template('question/question_edit.html', mc=mc, row=row,
                                   subjects=subjects, qtypes=qtypes, schooltypes=schooltypes,
                                   form=form, documents=documents, s3docsurl=s3docsurl)

        ctx_delta = form.get('ctx_delta') or '{"ops":[]}'
        ctx_plaintext = (form.get('ctx_plaintext') or '').strip()

        def to_int(v):
            if v is None or v == '':
                return None
            try:
                return int(v)
            except Exception:
                return None

        sbj_id = to_int(form.get('sbj_id'))
        qtp_id = to_int(form.get('qtp_id'))
        sct_id = to_int(form.get('sct_id'))
        difficulty = to_int(form.get('qtn_difficulty'))
        grade = to_int(form.get('qtn_grade'))
        notes = form.get('qtn_notes')

        ok = db_update_question_with_complextext(
            qtn_id=qtn_id,
            usr_id=g.user_id,
            title=title,
            sbj_id=sbj_id,
            qtp_id=qtp_id,
            sct_id=sct_id,
            difficulty=difficulty,
            grade=grade,
            notes=notes,
            ctx_delta_json=ctx_delta,
            ctx_plaintext=ctx_plaintext
        )

        if ok:
            # --- handle document removal (before AI gate so changes are always saved) ---
            existing_docs = db_get_documents_for_question(qtn_id)
            for doc in existing_docs:
                if request.form.get(f"remove_doc_{doc['doc_id']}"):
                    s3_key = db_delete_document(doc['doc_id'])
                    if s3_key:
                        delete_file_from_s3(s3_key, os.environ['AWS_DOCS_BUCKET_NAME'])

            # --- handle new document upload (before AI gate so image is always saved) ---
            doc_file = request.files.get('document')
            if doc_file and doc_file.filename:
                if doc_file.content_type not in ALLOWED_DOC_TYPES:
                    flash(_("Invalid file type. Allowed: JPG, PNG, HEIC, PDF."), "warning")
                else:
                    doc_file.seek(0, 2)
                    size_bytes = doc_file.tell()
                    doc_file.seek(0)
                    if size_bytes > MAX_DOC_SIZE:
                        flash(_("File too large. Max 10 MB."), "warning")
                    else:
                        # remove existing docs first (single-document mode)
                        remaining_docs = db_get_documents_for_question(qtn_id)
                        for doc in remaining_docs:
                            s3_key = db_delete_document(doc['doc_id'])
                            if s3_key:
                                delete_file_from_s3(s3_key, os.environ['AWS_DOCS_BUCKET_NAME'])

                        safe_name = secure_filename(doc_file.filename)
                        s3_key = f"documents/{qtn_id}/{uuid.uuid4().hex}_{safe_name}"
                        upload_document_to_s3(
                            doc_file, s3_key,
                            os.environ['AWS_DOCS_BUCKET_NAME'],
                            doc_file.content_type
                        )
                        doc_id = db_create_document(
                            qtn_id=qtn_id,
                            filename=safe_name,
                            s3_key=s3_key,
                            content_type=doc_file.content_type,
                            size_bytes=size_bytes,
                        )
                        if doc_file.content_type.startswith('image/') and \
                                doc_file.content_type not in ('image/heic', 'image/heif'):
                            try:
                                doc_file.seek(0)
                                extracted = extract_image_to_delta(doc_file.read(), doc_file.content_type)
                                if extracted:
                                    db_save_extracted_delta(doc_id, json.dumps(extracted['delta']))
                                    if not ctx_plaintext:
                                        ctx_plaintext = extracted.get('plaintext', '')
                            except Exception:
                                log.warning("Background image extraction failed for doc %s", doc_id, exc_info=True)

            # --- AI suitability gate ---
            is_quotable, student_hint, predictions = analyze_and_gate_question(
                tkt_id=row['tkt_id'], qtn_id=qtn_id,
                title=title, plaintext=ctx_plaintext,
                ctx_delta_json=ctx_delta,
                sbj_id=sbj_id, qtp_id=qtp_id, sct_id=sct_id,
                grade=grade, difficulty=difficulty,
            )
            if not is_quotable:
                db_set_needs_clarification(row['tkt_id'], student_hint)
                notify_student_needs_clarification(row['tkt_id'], student_hint)
                flash(_("Please review the feedback and update your question."), "warning")
                return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))

            # Use AI predictions for quoting if available
            q_sbj_id = predictions['sbj_id'] if predictions else sbj_id
            q_sct_id = predictions['sct_id'] if predictions else sct_id
            q_grade = predictions['grade'] if predictions else grade
            q_difficulty = predictions['difficulty'] if predictions else difficulty

            # re-quote the ticket with updated metadata
            quote = quote_from_question_data(
                sbj_id=q_sbj_id,
                qtp_id=qtp_id,
                sct_id=q_sct_id,
                grade=q_grade,
                difficulty=q_difficulty,
                plaintext=ctx_plaintext,
            )
            if quote["quote_signature"] != row.get('tkt_quote_signature'):
                new_state = TKT_NEEDS_REVIEW if quote["overflow"] else TKT_QUOTED
                db_apply_quote_to_ticket(
                    tkt_id=row['tkt_id'],
                    quote_points=quote["points"],
                    quote_version=quote["version"],
                    quote_note=quote["note"],
                    new_state=new_state,
                    quote_payload=quote["quote_payload"],
                    quote_signature=quote["quote_signature"],
                    quote_input=quote["quote_input"],
                )
                if new_state == TKT_QUOTED:
                    notify_student_quote_ready(row['tkt_id'])

            flash(_("Question updated."), "success")
            return redirect(url_for('bl_question.question_detail', qtn_id=qtn_id))
        else:
            flash(_("Update failed."), "danger")

    # GET: pre-fill from DB row
    documents = db_get_documents_for_question(qtn_id)
    s3docsurl = os.environ['AWS_DOCS_BUCKET_URL']
    return render_template('question/question_edit.html', mc=mc, row=row,
                           subjects=subjects, qtypes=qtypes, schooltypes=schooltypes,
                           form={}, documents=documents, s3docsurl=s3docsurl)
