# nightsquirrel/bl_references.py
# References module blueprint — Iterations 1 & 2.
# Iteration 1: Admin CRUD for references, persons, publishers.
# Iteration 2: Public library, My References (student/tutor), manage refs for questions/answers.

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, g, abort, jsonify)
from flask_babel import gettext as _
from flask_login import login_required
from psycopg2.extras import RealDictCursor as _RDC
from .auth import admin_required, tutor_required
from .db import get_db
from .db_references import (
    db_list_persons, db_get_person, db_create_person, db_update_person, db_delete_person,
    db_list_publishers, db_get_publisher, db_create_publisher, db_update_publisher, db_delete_publisher,
    db_get_book, db_create_book, db_update_book,
    db_get_article, db_create_article, db_update_article,
    db_get_video, db_create_video, db_update_video,
    db_get_weblink, db_create_weblink, db_update_weblink,
    db_list_references, db_get_reference, db_get_reference_fks, db_get_reference_typed_entity,
    db_create_reference, db_update_reference_meta, db_delete_reference,
    db_create_reference_image, db_delete_reference_image, db_set_reference_images,
    db_list_references_for_question, db_attach_reference_to_question, db_detach_reference_from_question,
    db_list_references_for_answer,   db_attach_reference_to_answer,   db_detach_reference_from_answer,
    db_find_person_by_name, db_find_publisher_by_name,
    db_set_ref_needs_review, db_clear_ref_needs_review,
    db_find_persons_by_familyname, db_find_publishers_by_name_fuzzy,
    db_toggle_ref_flag, db_list_leo_reading,
    db_list_references_by_person,
    db_list_outstanding_works_by_person,
    db_create_outstanding_work,
    db_list_references_by_tag,
    db_list_library_persons_with_refs,
)
from .s3_operations import upload_bytes_to_s3, delete_file_from_s3
from .db_tags import db_tags_for_refs_batch, db_list_tags_for_reference, db_list_tags_for_library
from .db_lookup import db_get_questiontypes
import os
import psycopg2
import requests
import json
from PIL import Image
from io import BytesIO

from .db_book_drafts import (db_create_book_draft, db_list_book_drafts, db_get_book_draft,
                              db_delete_book_draft, db_delete_draft_by_ref_id,
                              db_mark_draft_processed,
                              db_mark_draft_already_present, db_mark_draft_error,
                              db_flush_completed_drafts)

bp = Blueprint('bl_references', __name__, url_prefix='/references')

# S3 bucket for reference cover / thumbnail images (used from Iteration 3 onwards)
_REF_IMAGES_BUCKET_NAME = os.environ.get('AWS_REF_IMAGES_BUCKET_NAME', 'nightsquirrel-reference-images')
_REF_IMAGES_BUCKET_URL  = os.environ.get('AWS_REF_IMAGES_BUCKET_URL', '')

# Google Books API key (optional — without it the free quota is very small)
_GOOGLE_BOOKS_API_KEY = os.environ.get('GOOGLE_BOOKS_API_KEY', '')

# Reference type slug <-> rtp_id (must match tbl_r_reference_type seed data)
_RTP_ID   = {'book': 1, 'article': 2, 'video': 3, 'weblink': 4}
_RTP_SLUG = {1: 'book', 2: 'article', 3: 'video', 4: 'weblink'}


# ---------------------------------------------------------------------------
# Small form-parsing helpers
# ---------------------------------------------------------------------------

def _int(key, default=None):
    """Parse an optional integer from request.form."""
    v = request.form.get(key, '').strip()
    try:
        return int(v) if v else default
    except ValueError:
        return default


def _bool(key):
    """Return True if a checkbox key is present in request.form."""
    return key in request.form


def _str(key):
    """Return stripped string or None."""
    return request.form.get(key, '').strip() or None


# ---------------------------------------------------------------------------
# Helpers that build keyword-arg dicts for the typed-entity DB functions,
# keeping the POST handlers DRY.
# ---------------------------------------------------------------------------

def _book_kwargs():
    return dict(
        title=_str('bok_title'),
        subtitle=_str('bok_subtitle'),
        author1_per_id=_int('bok_author1_per_id'),
        author2_per_id=_int('bok_author2_per_id'),
        author_other=_str('bok_author_other'),
        author_etal=_bool('bok_author_etal'),
        editor1_per_id=_int('bok_editor1_per_id'),
        editor2_per_id=_int('bok_editor2_per_id'),
        editor_other=_str('bok_editor_other'),
        editor_etal=_bool('bok_editor_etal'),
        translator1_per_id=_int('bok_translator1_per_id'),
        translator2_per_id=_int('bok_translator2_per_id'),
        translator_other=_str('bok_translator_other'),
        translator_etal=_bool('bok_translator_etal'),
        year=_int('bok_year'),
        pub_id=_int('pub_id'),
        location=_str('bok_location'),
        isbn=_str('bok_isbn'),
        edition=_str('bok_edition'),
        language=_str('bok_language'),
        pages=_int('bok_pages'),
        link=_str('bok_link'),
    )


def _article_kwargs():
    return dict(
        title=_str('art_title'),
        author1_per_id=_int('art_author1_per_id'),
        author2_per_id=_int('art_author2_per_id'),
        author_other=_str('art_author_other'),
        author_etal=_bool('art_author_etal'),
        editor1_per_id=_int('art_editor1_per_id'),
        editor2_per_id=_int('art_editor2_per_id'),
        editor_other=_str('art_editor_other'),
        editor_etal=_bool('art_editor_etal'),
        date=_str('art_date'),
        pub_id=_int('pub_id'),
        location=_str('art_location'),
        doi=_str('art_doi'),
        container=_str('art_container'),
        issue=_str('art_issue'),
        language=_str('art_language'),
        link=_str('art_link'),
    )


def _video_kwargs():
    return dict(
        title=_str('vid_title'),
        editor=_str('vid_editor'),
        author1_per_id=_int('vid_author1_per_id'),
        date=_str('vid_date'),
        platform=_str('vid_platform'),
        language=_str('vid_language'),
        link=_str('vid_link'),
    )


def _weblink_kwargs():
    return dict(
        title=_str('wlk_title'),
        editor=_str('wlk_editor'),
        author1_per_id=_int('wlk_author1_per_id'),
        date=_str('wlk_date'),
        platform=_str('wlk_platform'),
        language=_str('wlk_language'),
        link=_str('wlk_link'),
    )


# ---------------------------------------------------------------------------
# Private ownership helpers (inline SQL, no new DB file needed)
# ---------------------------------------------------------------------------

def _question_for_student(qtn_id, usr_id):
    """Return minimal question row if usr_id owns it, else None."""
    cur = get_db().cursor(cursor_factory=_RDC)
    cur.execute("""
        SELECT qtn_id, qtn_title
          FROM nightsquirrel.tbl_q_question
         WHERE qtn_id = %s AND usr_id = %s AND qtn_is_valid = true
    """, (qtn_id, usr_id))
    return cur.fetchone()


def _answer_for_tutor(ans_id, tutor_usr_id):
    """Return answer+question info if tutor_usr_id is assigned to the ticket."""
    cur = get_db().cursor(cursor_factory=_RDC)
    cur.execute("""
        SELECT a.ans_id, a.tkt_id, q.qtn_title
          FROM nightsquirrel.tbl_q_answer a
          JOIN nightsquirrel.tbl_t_ticket  t ON t.tkt_id  = a.tkt_id
          JOIN nightsquirrel.tbl_q_question q ON q.qtn_id = a.qtn_id
         WHERE a.ans_id = %s AND t.tutor_usr_id = %s
    """, (ans_id, tutor_usr_id))
    return cur.fetchone()


def _load_entity(fks):
    """Load the typed entity row for a reference fks dict."""
    if fks['ref_bok_id']:
        return db_get_book(fks['ref_bok_id'])
    elif fks['ref_art_id']:
        return db_get_article(fks['ref_art_id'])
    elif fks['ref_vid_id']:
        return db_get_video(fks['ref_vid_id'])
    else:
        return db_get_weblink(fks['ref_wlk_id'])


def _save_typed_entity(rtp, fks):
    """Update the typed entity from form data. fks must be for an existing reference."""
    if rtp == 'book':
        db_update_book(bok_id=fks['ref_bok_id'], **_book_kwargs())
    elif rtp == 'article':
        db_update_article(art_id=fks['ref_art_id'], **_article_kwargs())
    elif rtp == 'video':
        db_update_video(vid_id=fks['ref_vid_id'], **_video_kwargs())
    else:
        db_update_weblink(wlk_id=fks['ref_wlk_id'], **_weblink_kwargs())


def _create_typed_entity_and_ref(rtp, usr_id, is_library=False, note=None):
    """Create typed entity + reference row. Returns ref_id."""
    if rtp == 'book':
        typed_id = db_create_book(usr_id=usr_id, **_book_kwargs())
        return db_create_reference(rtp_id=1, usr_id=usr_id, ref_bok_id=typed_id,
                                   is_library=is_library, note=note)
    elif rtp == 'article':
        typed_id = db_create_article(usr_id=usr_id, **_article_kwargs())
        return db_create_reference(rtp_id=2, usr_id=usr_id, ref_art_id=typed_id,
                                   is_library=is_library, note=note)
    elif rtp == 'video':
        typed_id = db_create_video(usr_id=usr_id, **_video_kwargs())
        return db_create_reference(rtp_id=3, usr_id=usr_id, ref_vid_id=typed_id,
                                   is_library=is_library, note=note)
    else:  # weblink
        typed_id = db_create_weblink(usr_id=usr_id, **_weblink_kwargs())
        return db_create_reference(rtp_id=4, usr_id=usr_id, ref_wlk_id=typed_id,
                                   is_library=is_library, note=note)


# =============================================================================
# QUICK-ADD — persons and publishers (login_required, used by student/tutor)
# =============================================================================

@bp.route('/persons/new', methods=['GET', 'POST'])
@login_required
def quick_new_person():
    next_url = request.args.get('next') or request.form.get('next') or url_for('bl_references.my_refs')
    if request.method == 'POST':
        try:
            db_create_person(
                firstname=_str('per_firstname'),
                familyname=_str('per_familyname'),
                caption_ita=_str('per_caption_ita'),
                caption_eng=_str('per_caption_eng'),
                strings=_str('per_strings'),
            )
            flash(_('Person added.'), 'success')
            return redirect(next_url)
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/references/person_form.html',
                           mc={'my_refs': 'active'}, row=None,
                           action=url_for('bl_references.quick_new_person', next=next_url))


@bp.route('/publishers/new', methods=['GET', 'POST'])
@login_required
def quick_new_publisher():
    next_url = request.args.get('next') or request.form.get('next') or url_for('bl_references.my_refs')
    if request.method == 'POST':
        try:
            db_create_publisher(
                name=_str('pub_name') or '',
                othername=_str('pub_othername'),
                location=_str('pub_location'),
                description=_str('pub_description'),
            )
            flash(_('Publisher added.'), 'success')
            return redirect(next_url)
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/references/publisher_form.html',
                           mc={'my_refs': 'active'}, row=None,
                           action=url_for('bl_references.quick_new_publisher', next=next_url))


# =============================================================================
# PUBLIC — LIBRARY
# =============================================================================

@bp.route('/<int:ref_id>')
@login_required
def ref_detail(ref_id):
    ref = db_get_reference(ref_id)
    if not ref:
        abort(404)
    entity = db_get_reference_typed_entity(ref_id)
    ref_tags = db_list_tags_for_reference(ref_id)
    qtypes = db_get_questiontypes()
    return render_template('references/ref_detail.html',
                           mc={}, ref=ref, entity=entity, ref_tags=ref_tags,
                           qtypes=qtypes,
                           images_bucket_url=_REF_IMAGES_BUCKET_URL)


@bp.route('/library')
def library():
    q          = (request.args.get('q') or '').strip()
    rtp_filter = (request.args.get('rtp') or '').strip()
    crucial    = request.args.get('crucial') == '1'
    rtp_id     = _RTP_ID.get(rtp_filter) if rtp_filter else None
    refs       = db_list_references(library_only=True, rtp_id=rtp_id, q=q or None, crucial_only=crucial)
    tags_by_ref  = db_tags_for_refs_batch([r['ref_id'] for r in refs])
    library_tags = db_list_tags_for_library()
    return render_template(
        'references/library.html',
        mc={'library': 'active'},
        refs=refs, q=q, rtp_filter=rtp_filter, crucial=crucial,
        tags_by_ref=tags_by_ref,
        library_tags=library_tags,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/people')
def people():
    q = (request.args.get('q') or '').strip()
    persons_with_refs = db_list_library_persons_with_refs(q=q or None)
    return render_template(
        'references/people.html',
        mc={'library': 'active'},
        persons_with_refs=persons_with_refs,
        q=q,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/person/<int:per_id>')
def person_page(per_id: int):
    person = db_get_person(per_id)
    if not person:
        abort(404)
    is_admin = getattr(g, 'usr_is_admin', False)
    refs = db_list_references_by_person(per_id, library_only=not is_admin)
    outstanding = db_list_outstanding_works_by_person(per_id)
    tags_by_ref = db_tags_for_refs_batch([r['ref_id'] for r in refs]) if refs else {}
    return render_template(
        'references/person.html',
        mc={'library': 'active'},
        person=person,
        refs=refs,
        outstanding=outstanding,
        tags_by_ref=tags_by_ref,
        is_admin=is_admin,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/tag/<int:tag_id>')
def tag_page(tag_id: int):
    from .db_tags import db_get_tag
    tag = db_get_tag(tag_id)
    if not tag:
        abort(404)
    refs = db_list_references_by_tag(tag_id)
    tags_by_ref = db_tags_for_refs_batch([r['ref_id'] for r in refs]) if refs else {}
    return render_template(
        'references/tag.html',
        mc={'library': 'active'},
        tag=tag,
        refs=refs,
        tags_by_ref=tags_by_ref,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


# =============================================================================
# MY REFERENCES  (login_required — student & tutor)
# =============================================================================

@bp.route('/my')
@login_required
def my_refs():
    refs = db_list_references(usr_id=g.user_id)
    return render_template('references/my_refs.html',
                           mc={'my_refs': 'active'}, refs=refs,
                           images_bucket_url=_REF_IMAGES_BUCKET_URL)


@bp.route('/my/new')
@login_required
def my_new_choose_type():
    return render_template('admin/references/choose_type.html',
                           mc={'my_refs': 'active'},
                           back_url=url_for('bl_references.my_refs'),
                           url_book=url_for('bl_references.my_new_ref', rtp='book'),
                           url_article=url_for('bl_references.my_new_ref', rtp='article'),
                           url_video=url_for('bl_references.my_new_ref', rtp='video'),
                           url_weblink=url_for('bl_references.my_new_ref', rtp='weblink'))


@bp.route('/my/new/<rtp>', methods=['GET', 'POST'])
@login_required
def my_new_ref(rtp):
    if rtp not in _RTP_ID:
        abort(404)
    persons    = db_list_persons()
    publishers = db_list_publishers()

    if request.method == 'POST':
        try:
            _create_typed_entity_and_ref(rtp, usr_id=g.user_id)
            flash(_('Reference created.'), 'success')
            return redirect(url_for('bl_references.my_refs'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={'my_refs': 'active'},
        rtp=rtp, row=None, entity=None,
        persons=persons, publishers=publishers,
        show_library_meta=False, show_quick_add=True,
        cancel_url=url_for('bl_references.my_refs'),
        action=url_for('bl_references.my_new_ref', rtp=rtp),
    )


@bp.route('/my/<int:ref_id>/edit', methods=['GET', 'POST'])
@login_required
def my_edit_ref(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks or fks['usr_id'] != g.user_id:
        abort(404)

    rtp         = _RTP_SLUG.get(fks['rtp_id'])
    persons     = db_list_persons()
    publishers  = db_list_publishers()
    entity      = _load_entity(fks)
    ref_summary = db_get_reference(ref_id)

    if request.method == 'POST':
        try:
            _save_typed_entity(rtp, fks)
            flash(_('Reference updated.'), 'success')
            return redirect(url_for('bl_references.my_refs'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={'my_refs': 'active'},
        rtp=rtp, row=fks, entity=entity,
        persons=persons, publishers=publishers,
        show_library_meta=False, show_quick_add=True,
        cancel_url=url_for('bl_references.my_refs'),
        action=url_for('bl_references.my_edit_ref', ref_id=ref_id),
        cover_s3_key=ref_summary['cover_s3_key'] if ref_summary else None,
        thumbnail_s3_key=ref_summary['thumbnail_s3_key'] if ref_summary else None,
        ref_images_url=_REF_IMAGES_BUCKET_URL,
        upload_cover_url=url_for('bl_references.my_upload_cover', ref_id=ref_id),
        upload_thumbnail_url=url_for('bl_references.my_upload_thumbnail', ref_id=ref_id),
        delete_cover_url=url_for('bl_references.my_delete_image', ref_id=ref_id, slot='cover'),
        delete_thumbnail_url=url_for('bl_references.my_delete_image', ref_id=ref_id, slot='thumbnail'),
    )


@bp.post('/my/<int:ref_id>/delete')
@login_required
def my_delete_ref(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks or fks['usr_id'] != g.user_id:
        abort(404)
    try:
        s3_keys = db_delete_reference(ref_id)
        for key in (s3_keys.get('cover_s3_key'), s3_keys.get('thumbnail_s3_key')):
            if key:
                delete_file_from_s3(key, _REF_IMAGES_BUCKET_NAME)
        flash(_('Reference deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Cannot delete reference: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.my_refs'))


# =============================================================================
# QUESTION REFS  (login_required + student ownership)
# =============================================================================

def _attached_ids(refs):
    return {r['ref_id'] for r in refs}


@bp.route('/question/<int:qtn_id>')
@login_required
def manage_question_refs(qtn_id):
    qtn = _question_for_student(qtn_id, g.user_id)
    if not qtn:
        abort(404)

    attached = db_list_references_for_question(qtn_id)
    att_ids  = _attached_ids(attached)
    own      = [r for r in db_list_references(usr_id=g.user_id)        if r['ref_id'] not in att_ids]
    library  = [r for r in db_list_references(library_only=True)       if r['ref_id'] not in att_ids]

    return render_template(
        'references/manage_refs.html',
        mc={},
        context='question', parent_id=qtn_id,
        parent_title=qtn['qtn_title'],
        attached=attached, own=own, library=library,
        new_url=url_for('bl_references.question_new_choose_type', qtn_id=qtn_id),
        back_url=url_for('bl_question.question_detail', qtn_id=qtn_id),
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/question/<int:qtn_id>/new')
@login_required
def question_new_choose_type(qtn_id):
    if not _question_for_student(qtn_id, g.user_id):
        abort(404)
    return render_template('admin/references/choose_type.html',
                           mc={},
                           back_url=url_for('bl_references.manage_question_refs', qtn_id=qtn_id),
                           url_book=url_for('bl_references.question_new_ref', qtn_id=qtn_id, rtp='book'),
                           url_article=url_for('bl_references.question_new_ref', qtn_id=qtn_id, rtp='article'),
                           url_video=url_for('bl_references.question_new_ref', qtn_id=qtn_id, rtp='video'),
                           url_weblink=url_for('bl_references.question_new_ref', qtn_id=qtn_id, rtp='weblink'))


@bp.route('/question/<int:qtn_id>/new/<rtp>', methods=['GET', 'POST'])
@login_required
def question_new_ref(qtn_id, rtp):
    if rtp not in _RTP_ID or not _question_for_student(qtn_id, g.user_id):
        abort(404)
    persons    = db_list_persons()
    publishers = db_list_publishers()

    if request.method == 'POST':
        try:
            ref_id = _create_typed_entity_and_ref(rtp, usr_id=g.user_id)
            db_attach_reference_to_question(ref_id, qtn_id)
            flash(_('Reference created and attached.'), 'success')
            return redirect(url_for('bl_references.manage_question_refs', qtn_id=qtn_id))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={},
        rtp=rtp, row=None, entity=None,
        persons=persons, publishers=publishers,
        show_library_meta=False, show_quick_add=True,
        cancel_url=url_for('bl_references.manage_question_refs', qtn_id=qtn_id),
        action=url_for('bl_references.question_new_ref', qtn_id=qtn_id, rtp=rtp),
    )


@bp.post('/question/<int:qtn_id>/attach/<int:ref_id>')
@login_required
def question_attach_ref(qtn_id, ref_id):
    if not _question_for_student(qtn_id, g.user_id):
        abort(404)
    try:
        db_attach_reference_to_question(ref_id, qtn_id)
    except psycopg2.Error as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.manage_question_refs', qtn_id=qtn_id))


@bp.post('/question/<int:qtn_id>/detach/<int:ref_id>')
@login_required
def question_detach_ref(qtn_id, ref_id):
    if not _question_for_student(qtn_id, g.user_id):
        abort(404)
    try:
        db_detach_reference_from_question(ref_id, qtn_id)
    except psycopg2.Error as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.manage_question_refs', qtn_id=qtn_id))


# =============================================================================
# ANSWER REFS  (tutor_required + tutor ownership via ticket)
# =============================================================================

@bp.route('/answer/<int:ans_id>')
@tutor_required
def manage_answer_refs(ans_id):
    ans = _answer_for_tutor(ans_id, g.user_id)
    if not ans:
        abort(404)

    attached = db_list_references_for_answer(ans_id)
    att_ids  = _attached_ids(attached)
    own      = [r for r in db_list_references(usr_id=g.user_id)  if r['ref_id'] not in att_ids]
    library  = [r for r in db_list_references(library_only=True) if r['ref_id'] not in att_ids]

    return render_template(
        'references/manage_refs.html',
        mc={'tutor': 'active'},
        context='answer', parent_id=ans_id,
        parent_title=ans['qtn_title'],
        attached=attached, own=own, library=library,
        new_url=url_for('bl_references.answer_new_choose_type', ans_id=ans_id),
        back_url=url_for('bl_tutor.ticket_detail', tkt_id=ans['tkt_id']),
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/answer/<int:ans_id>/new')
@tutor_required
def answer_new_choose_type(ans_id):
    if not _answer_for_tutor(ans_id, g.user_id):
        abort(404)
    return render_template('admin/references/choose_type.html',
                           mc={'tutor': 'active'},
                           back_url=url_for('bl_references.manage_answer_refs', ans_id=ans_id),
                           url_book=url_for('bl_references.answer_new_ref', ans_id=ans_id, rtp='book'),
                           url_article=url_for('bl_references.answer_new_ref', ans_id=ans_id, rtp='article'),
                           url_video=url_for('bl_references.answer_new_ref', ans_id=ans_id, rtp='video'),
                           url_weblink=url_for('bl_references.answer_new_ref', ans_id=ans_id, rtp='weblink'))


@bp.route('/answer/<int:ans_id>/new/<rtp>', methods=['GET', 'POST'])
@tutor_required
def answer_new_ref(ans_id, rtp):
    if rtp not in _RTP_ID or not _answer_for_tutor(ans_id, g.user_id):
        abort(404)
    persons    = db_list_persons()
    publishers = db_list_publishers()

    if request.method == 'POST':
        try:
            ref_id = _create_typed_entity_and_ref(rtp, usr_id=g.user_id)
            db_attach_reference_to_answer(ref_id, ans_id)
            flash(_('Reference created and attached.'), 'success')
            return redirect(url_for('bl_references.manage_answer_refs', ans_id=ans_id))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={'tutor': 'active'},
        rtp=rtp, row=None, entity=None,
        persons=persons, publishers=publishers,
        show_library_meta=False, show_quick_add=True,
        cancel_url=url_for('bl_references.manage_answer_refs', ans_id=ans_id),
        action=url_for('bl_references.answer_new_ref', ans_id=ans_id, rtp=rtp),
    )


@bp.post('/answer/<int:ans_id>/attach/<int:ref_id>')
@tutor_required
def answer_attach_ref(ans_id, ref_id):
    if not _answer_for_tutor(ans_id, g.user_id):
        abort(404)
    try:
        db_attach_reference_to_answer(ref_id, ans_id)
    except psycopg2.Error as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.manage_answer_refs', ans_id=ans_id))


@bp.post('/answer/<int:ans_id>/detach/<int:ref_id>')
@tutor_required
def answer_detach_ref(ans_id, ref_id):
    if not _answer_for_tutor(ans_id, g.user_id):
        abort(404)
    try:
        db_detach_reference_from_answer(ref_id, ans_id)
    except psycopg2.Error as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.manage_answer_refs', ans_id=ans_id))


# =============================================================================
# ADMIN — REFERENCES LIST
# =============================================================================

@bp.route('/admin')
@admin_required
def admin_list():
    q             = (request.args.get('q') or '').strip()
    rtp_filter    = (request.args.get('rtp') or '').strip()
    review_filter = request.args.get('review') == '1'
    rtp_id        = _RTP_ID.get(rtp_filter) if rtp_filter else None
    refs          = db_list_references(rtp_id=rtp_id, q=q or None,
                                       needs_review=True if review_filter else None)
    return render_template(
        'admin/references/list.html',
        mc={'admin': 'active'},
        refs=refs, q=q, rtp_filter=rtp_filter, review_filter=review_filter,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


@bp.route('/admin/<int:ref_id>/clear-review', methods=['POST'])
@admin_required
def admin_clear_needs_review(ref_id):
    db_clear_ref_needs_review(ref_id)
    db_delete_draft_by_ref_id(ref_id)
    return redirect(request.referrer or url_for('bl_references.admin_list'))


# =============================================================================
# ADMIN — NEW REFERENCE  (choose type → type-specific form)
# =============================================================================

@bp.route('/admin/new')
@admin_required
def admin_new_choose_type():
    return render_template('admin/references/choose_type.html',
                           mc={'admin': 'active'},
                           back_url=url_for('bl_references.admin_list'),
                           url_book=url_for('bl_references.admin_new_ref', rtp='book'),
                           url_book_scan=url_for('bl_references.admin_scan_isbn'),
                           url_article=url_for('bl_references.admin_new_ref', rtp='article'),
                           url_video=url_for('bl_references.admin_new_ref', rtp='video'),
                           url_weblink=url_for('bl_references.admin_new_ref', rtp='weblink'))


@bp.route('/admin/new/<rtp>', methods=['GET', 'POST'])
@admin_required
def admin_new_ref(rtp):
    if rtp not in _RTP_ID:
        abort(404)

    persons    = db_list_persons()
    publishers = db_list_publishers()

    if request.method == 'POST':
        try:
            ref_id = _create_typed_entity_and_ref(
                rtp, usr_id=g.user_id,
                is_library=_bool('ref_is_library'),
                note=_str('ref_note'),
            )
            if _bool('ref_needs_review'):
                db_set_ref_needs_review(ref_id)
            flash(_('Reference created.'), 'success')
            return redirect(url_for('bl_references.admin_list'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={'admin': 'active'},
        rtp=rtp, row=None, entity=None,
        persons=persons, publishers=publishers,
        show_quick_add=False,
        cancel_url=url_for('bl_references.admin_list'),
        action=url_for('bl_references.admin_new_ref', rtp=rtp),
    )


# =============================================================================
# ADMIN — ISBN SCAN PIPELINE
# =============================================================================

_OL_HEADERS = {'User-Agent': 'NightSquirrel/1.0 (educational app; contact admin@nightsquirrels.it)'}


def _lookup_isbn(isbn: str) -> dict:
    """Query Google Books (primary, needs API key) then Open Library (fallback).
    Returns: {found, source, title, year, isbn, publisher, authors[], cover_url, raw_data}
    On API error returns: {found: False, error: str}
    """
    import re
    isbn_clean = isbn.replace('-', '').replace(' ', '')
    errors = []

    # --- Google Books (primary when API key is available) ---
    try:
        params = {'q': f'isbn:{isbn_clean}'}
        if _GOOGLE_BOOKS_API_KEY:
            params['key'] = _GOOGLE_BOOKS_API_KEY
        r = requests.get('https://www.googleapis.com/books/v1/volumes',
                         params=params, timeout=6)
        if r.status_code == 200:
            data = r.json()
            items = data.get('items', [])
            if items:
                # The search result strips publisher; fetch the full volume record
                self_link = items[0].get('selfLink', '')
                if self_link and _GOOGLE_BOOKS_API_KEY:
                    try:
                        r2 = requests.get(self_link,
                                          params={'key': _GOOGLE_BOOKS_API_KEY}, timeout=6)
                        if r2.status_code == 200:
                            items[0] = r2.json()
                    except Exception:
                        pass
                info = items[0].get('volumeInfo', {})
                cover_url = info.get('imageLinks', {}).get('thumbnail', '')
                if cover_url.startswith('http:'):
                    cover_url = 'https:' + cover_url[5:]
                year = (info.get('publishedDate', '') or '')[:4]
                pages = info.get('pageCount')
                return {'found': True, 'source': 'googlebooks',
                        'title': info.get('title', ''),
                        'subtitle': info.get('subtitle', ''),
                        'year': year if year.isdigit() else None,
                        'isbn': isbn_clean,
                        'publisher': info.get('publisher', ''),
                        'authors': info.get('authors', []),
                        'pages': int(pages) if pages else None,
                        'cover_url': cover_url, 'raw_data': data}
        elif r.status_code == 429:
            errors.append('Google Books: quota exceeded (add GOOGLE_BOOKS_API_KEY)')
        elif r.status_code != 200:
            errors.append(f'Google Books: HTTP {r.status_code}')
    except Exception as e:
        errors.append(f'Google Books: {e}')

    # --- Open Library (fallback) ---
    try:
        r = requests.get(
            f'https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data',
            headers=_OL_HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            key = f'ISBN:{isbn_clean}'
            if key in data:
                book = data[key]
                authors    = [a['name'] for a in book.get('authors', [])]
                publishers = [p['name'] for p in book.get('publishers', [])]
                cover_url  = (book.get('cover', {}).get('large')
                              or book.get('cover', {}).get('medium') or '')
                m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', book.get('publish_date', ''))
                pages = book.get('number_of_pages')
                return {'found': True, 'source': 'openlibrary',
                        'title': book.get('title', ''),
                        'subtitle': book.get('subtitle', ''),
                        'year': m.group(1) if m else None,
                        'isbn': isbn_clean,
                        'publisher': publishers[0] if publishers else '',
                        'authors': authors,
                        'pages': int(pages) if pages else None,
                        'cover_url': cover_url, 'raw_data': data}
        elif r.status_code != 200:
            errors.append(f'Open Library: HTTP {r.status_code}')
    except Exception as e:
        errors.append(f'Open Library: {e}')

    if errors:
        return {'found': False, 'error': '; '.join(errors)}
    return {'found': False}


@bp.route('/admin/scan-isbn')
@admin_required
def admin_scan_isbn():
    return render_template('admin/references/isbn_scan.html',
                           mc={'admin': 'active'},
                           lookup_url=url_for('bl_references.admin_lookup_isbn'),
                           save_url=url_for('bl_references.admin_save_isbn_draft'),
                           back_url=url_for('bl_references.admin_new_choose_type'))


@bp.route('/admin/lookup-isbn')
@admin_required
def admin_lookup_isbn():
    isbn = request.args.get('isbn', '').strip()
    if not isbn:
        return jsonify({'found': False, 'error': 'No ISBN provided'})
    return jsonify(_lookup_isbn(isbn))


@bp.route('/admin/scan-isbn/save', methods=['POST'])
@admin_required
def admin_save_isbn_draft():
    isbn      = request.form.get('isbn', '').strip()
    cover_url = request.form.get('cover_url', '').strip() or None
    try:
        raw_data = json.loads(request.form.get('raw_data', '{}'))
    except ValueError:
        raw_data = {}
    db_create_book_draft(isbn, raw_data, cover_url)
    flash(_('Draft saved.'), 'success')
    return redirect(url_for('bl_references.admin_draft_list'))


def _draft_display_title(draft: dict) -> str:
    raw  = draft.get('raw_data') or {}
    isbn = draft.get('isbn', '')
    if f'ISBN:{isbn}' in raw:
        return raw[f'ISBN:{isbn}'].get('title', '')
    items = raw.get('items', [])
    if items:
        return items[0].get('volumeInfo', {}).get('title', '')
    return ''


def _parse_author_name(full_name: str) -> tuple[str, str]:
    """Split 'Firstname Familyname' → (firstname, familyname).
    Single token → ('', token). Handles 'Last, First' format too.
    """
    s = full_name.strip()
    if ',' in s:
        parts = [p.strip() for p in s.split(',', 1)]
        return parts[1], parts[0]
    tokens = s.split()
    if len(tokens) == 1:
        return '', tokens[0]
    return ' '.join(tokens[:-1]), tokens[-1]


def _ai_find_person(api_name: str, candidates: list) -> int | None:
    """Ask Claude Haiku to match api_name against DB candidates. Returns per_id or None."""
    if not candidates:
        return None
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
    lines = '\n'.join(
        f"  {c['per_id']}: {(c['per_firstname'] or '').strip()} {(c['per_familyname'] or '').strip()}"
        for c in candidates
    )
    msg = (f'Author name from book API: "{api_name}"\n'
           f'Existing persons in database:\n{lines}\n\n'
           f'If one of these is clearly the same person, reply with just their ID number. '
           f'If unsure or no match, reply with "none".')
    try:
        response = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=10,
            messages=[{'role': 'user', 'content': msg}])
        text = response.content[0].text.strip()
        return int(text)
    except Exception:
        return None


def _ai_find_publisher(api_name: str, candidates: list) -> int | None:
    """Ask Claude Haiku to match api_name against DB publisher candidates. Returns pub_id or None."""
    if not candidates:
        return None
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
    lines = '\n'.join(f"  {c['pub_id']}: {c['pub_name']}" for c in candidates)
    msg = (f'Publisher name from book API: "{api_name}"\n'
           f'Existing publishers in database:\n{lines}\n\n'
           f'If one of these is clearly the same publisher, reply with just their ID number. '
           f'If unsure or no match, reply with "none".')
    try:
        response = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=10,
            messages=[{'role': 'user', 'content': msg}])
        text = response.content[0].text.strip()
        return int(text)
    except Exception:
        return None


def _process_book_draft(draft: dict, usr_id: int) -> None:
    """Core processing engine. Raises on unrecoverable error."""
    import re
    isbn  = draft['isbn']
    title = _draft_display_title(draft)
    raw   = draft.get('raw_data') or {}

    # extract fields from raw_data
    key = f'ISBN:{isbn}'
    if key in raw:                          # Open Library format
        book_raw   = raw[key]
        authors    = [a['name'] for a in book_raw.get('authors', [])]
        publishers = [p['name'] for p in book_raw.get('publishers', [])]
        pub_name   = publishers[0] if publishers else ''
        subtitle   = book_raw.get('subtitle', '') or ''
        m    = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', book_raw.get('publish_date', ''))
        year  = int(m.group(1)) if m else None
        _p    = book_raw.get('number_of_pages')
        pages = int(_p) if _p else None
    else:                                   # Google Books format
        items    = raw.get('items', [])
        info     = items[0].get('volumeInfo', {}) if items else {}
        authors  = info.get('authors', [])
        pub_name = info.get('publisher', '')
        subtitle = info.get('subtitle', '') or ''
        y        = (info.get('publishedDate', '') or '')[:4]
        year     = int(y) if y.isdigit() else None
        _p       = info.get('pageCount')
        pages    = int(_p) if _p else None

    # duplicate check
    db = get_db()
    cur = db.cursor(cursor_factory=_RDC)
    cur.execute(
        "SELECT bok_id FROM nightsquirrel.tbl_r_book WHERE bok_isbn = %s LIMIT 1",
        (isbn,))
    if cur.fetchone():
        db_mark_draft_already_present(draft['draft_id'])
        return

    # person matching / creation  (exact → AI fuzzy → create new)
    needs_review = True  # ISBN imports always need human review
    author_ids   = []
    for name_str in authors[:4]:
        firstname, familyname = _parse_author_name(name_str)
        per_id = db_find_person_by_name(firstname, familyname)
        if per_id is None and familyname:
            candidates = db_find_persons_by_familyname(familyname)
            per_id = _ai_find_person(name_str, candidates)
        if per_id is None:
            per_id = db_create_person(firstname, familyname, strings=name_str)
        author_ids.append(per_id)
    while len(author_ids) < 4:
        author_ids.append(None)
    author_etal = len(authors) > 4

    # publisher matching / creation  (exact → AI fuzzy → create new)
    pub_id = None
    if pub_name:
        pub_id = db_find_publisher_by_name(pub_name)
        if pub_id is None:
            candidates = db_find_publishers_by_name_fuzzy(pub_name)
            pub_id = _ai_find_publisher(pub_name, candidates)
        if pub_id is None:
            pub_id = db_create_publisher(pub_name)

    # create book + reference
    bok_id = db_create_book(
        usr_id=usr_id, title=title, subtitle=subtitle or None, isbn=isbn, year=year, pub_id=pub_id,
        author1_per_id=author_ids[0], author2_per_id=author_ids[1],
        author_other=', '.join(authors[2:4]) or None,
        author_etal=author_etal,
        pages=pages,
    )
    ref_id = db_create_reference(rtp_id=1, usr_id=usr_id,
                                  ref_bok_id=bok_id, is_library=True)
    if needs_review:
        db_set_ref_needs_review(ref_id)

    # cover image (non-fatal if it fails)
    cover_url = draft.get('cover_url') or ''
    if cover_url:
        try:
            r = requests.get(cover_url, timeout=10)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert('RGB')

            cover_buf = BytesIO()
            img.save(cover_buf, format='JPEG', quality=85)
            cover_data = cover_buf.getvalue()
            cover_key  = f'refs/{ref_id}/cover.jpg'
            upload_bytes_to_s3(cover_data, cover_key,
                               _REF_IMAGES_BUCKET_NAME, 'image/jpeg')
            cover_img_id = db_create_reference_image(
                f'cover_{ref_id}.jpg', cover_key, 'image/jpeg', len(cover_data))

            w, h = img.size
            thumb = img.resize((200, int(h * 200 / w)), Image.LANCZOS)
            thumb_buf = BytesIO()
            thumb.save(thumb_buf, format='JPEG', quality=75)
            thumb_data = thumb_buf.getvalue()
            thumb_key  = f'refs/{ref_id}/thumb.jpg'
            upload_bytes_to_s3(thumb_data, thumb_key,
                               _REF_IMAGES_BUCKET_NAME, 'image/jpeg')
            thumb_img_id = db_create_reference_image(
                f'thumb_{ref_id}.jpg', thumb_key, 'image/jpeg', len(thumb_data))

            db_set_reference_images(ref_id, cover_img_id, thumb_img_id)
        except Exception:
            log.exception("_process_book_draft: cover upload failed for ref_id=%s cover_url=%s",
                          ref_id, cover_url)

    db_mark_draft_processed(draft['draft_id'], ref_id)


@bp.route('/admin/drafts/<int:draft_id>/process', methods=['POST'])
@admin_required
def admin_process_draft(draft_id):
    draft = db_get_book_draft(draft_id)
    if not draft:
        abort(404)
    try:
        _process_book_draft(draft, g.user_id)
        flash(_('Draft processed.'), 'success')
    except Exception as e:
        db_mark_draft_error(draft_id, str(e))
        flash(_('Processing failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_draft_list'))


@bp.route('/admin/drafts')
@admin_required
def admin_draft_list():
    show   = request.args.get('show', 'pending')
    drafts = db_list_book_drafts(processed=None if show == 'all' else False)
    for d in drafts:
        d['_title'] = _draft_display_title(d)
    return render_template('admin/references/draft_list.html',
                           mc={'admin': 'active'}, drafts=drafts, show=show)


@bp.route('/admin/drafts/<int:draft_id>/delete', methods=['POST'])
@admin_required
def admin_delete_draft(draft_id):
    db_delete_book_draft(draft_id)
    flash(_('Draft deleted.'), 'success')
    return redirect(url_for('bl_references.admin_draft_list'))


@bp.post('/admin/drafts/flush')
@admin_required
def admin_flush_drafts():
    count = db_flush_completed_drafts()
    flash(_('%(n)d completed draft(s) deleted.', n=count), 'success')
    return redirect(url_for('bl_references.admin_draft_list'))


# =============================================================================
# ADMIN — EDIT REFERENCE
# =============================================================================

@bp.route('/admin/<int:ref_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_ref(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)

    rtp = _RTP_SLUG.get(fks['rtp_id'])
    if not rtp:
        abort(404)

    persons    = db_list_persons()
    publishers = db_list_publishers()
    entity     = _load_entity(fks)
    ref_summary = db_get_reference(ref_id)

    if request.method == 'POST':
        try:
            _save_typed_entity(rtp, fks)
            db_update_reference_meta(ref_id=ref_id,
                                     is_library=_bool('ref_is_library'),
                                     note=_str('ref_note'),
                                     is_other_outstanding_work=_bool('ref_is_other_outstanding_work'))
            if _bool('ref_needs_review'):
                db_set_ref_needs_review(ref_id)
            else:
                db_clear_ref_needs_review(ref_id)
            flash(_('Reference updated.'), 'success')
            return redirect(url_for('bl_references.admin_list'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')

    return render_template(
        'admin/references/ref_form.html',
        mc={'admin': 'active'},
        rtp=rtp, row=fks, entity=entity,
        persons=persons, publishers=publishers,
        show_quick_add=False,
        cancel_url=url_for('bl_references.admin_list'),
        action=url_for('bl_references.admin_edit_ref', ref_id=ref_id),
        cover_s3_key=ref_summary['cover_s3_key'] if ref_summary else None,
        thumbnail_s3_key=ref_summary['thumbnail_s3_key'] if ref_summary else None,
        ref_images_url=_REF_IMAGES_BUCKET_URL,
        upload_cover_url=url_for('bl_references.admin_upload_cover', ref_id=ref_id),
        upload_thumbnail_url=url_for('bl_references.admin_upload_thumbnail', ref_id=ref_id),
        delete_cover_url=url_for('bl_references.admin_delete_image', ref_id=ref_id, slot='cover'),
        delete_thumbnail_url=url_for('bl_references.admin_delete_image', ref_id=ref_id, slot='thumbnail'),
    )


# =============================================================================
# ADMIN — DELETE REFERENCE
# =============================================================================

@bp.post('/admin/<int:ref_id>/delete')
@admin_required
def admin_delete_ref(ref_id):
    if not db_get_reference_fks(ref_id):
        abort(404)
    try:
        s3_keys = db_delete_reference(ref_id)
        for key in (s3_keys.get('cover_s3_key'), s3_keys.get('thumbnail_s3_key')):
            if key:
                delete_file_from_s3(key, _REF_IMAGES_BUCKET_NAME)
        flash(_('Reference deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Cannot delete reference: %(msg)s', msg=str(e)), 'danger')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


# =============================================================================
# ADMIN — TOGGLE LIBRARY FLAG  (quick action from list page)
# =============================================================================

@bp.post('/admin/<int:ref_id>/toggle-library')
@admin_required
def admin_toggle_library(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)
    try:
        db_update_reference_meta(ref_id=ref_id,
                                 is_library=not fks['ref_is_library'],
                                 note=fks['ref_note'])
    except psycopg2.Error as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


@bp.post('/admin/<int:ref_id>/toggle-current')
@admin_required
def admin_toggle_current(ref_id):
    db_toggle_ref_flag(ref_id, 'ref_is_current')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


@bp.post('/admin/<int:ref_id>/toggle-recent')
@admin_required
def admin_toggle_recent(ref_id):
    db_toggle_ref_flag(ref_id, 'ref_is_recent')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


@bp.post('/admin/<int:ref_id>/toggle-crucial')
@admin_required
def admin_toggle_crucial(ref_id):
    db_toggle_ref_flag(ref_id, 'ref_is_crucial')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


@bp.post('/admin/<int:ref_id>/toggle-outstanding')
@admin_required
def admin_toggle_outstanding(ref_id):
    db_toggle_ref_flag(ref_id, 'ref_is_other_outstanding_work')
    return redirect(request.referrer or url_for('bl_references.admin_list'))


@bp.route('/reading')
def leo_reading():
    current, recent = db_list_leo_reading()
    tags_current = db_tags_for_refs_batch([r['ref_id'] for r in current])
    tags_recent  = db_tags_for_refs_batch([r['ref_id'] for r in recent])
    return render_template(
        'references/leo_reading.html',
        mc={'leo_reading': 'active'},
        current=current, recent=recent,
        tags_current=tags_current, tags_recent=tags_recent,
        images_bucket_url=_REF_IMAGES_BUCKET_URL,
    )


# =============================================================================
# MY REFS — COVER / THUMBNAIL IMAGE UPLOAD  (login_required + ownership)
# =============================================================================

@bp.post('/my/<int:ref_id>/delete-image/<slot>')
@login_required
def my_delete_image(ref_id, slot):
    if slot not in ('cover', 'thumbnail'):
        abort(404)
    fks = db_get_reference_fks(ref_id)
    if not fks or fks['usr_id'] != g.user_id:
        abort(404)
    try:
        img_id = fks['ref_cover_img_id'] if slot == 'cover' else fks['ref_thumbnail_img_id']
        if img_id:
            new_cover = None if slot == 'cover' else fks['ref_cover_img_id']
            new_thumb = None if slot == 'thumbnail' else fks['ref_thumbnail_img_id']
            db_set_reference_images(ref_id, cover_img_id=new_cover, thumbnail_img_id=new_thumb)
            old_key = db_delete_reference_image(img_id)
            if old_key:
                delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Image removed.'), 'success')
    except Exception as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.my_edit_ref', ref_id=ref_id))


@bp.post('/my/<int:ref_id>/upload-cover')
@login_required
def my_upload_cover(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks or fks['usr_id'] != g.user_id:
        abort(404)
    try:
        img_id, _key = _upload_ref_image(ref_id, 'cover')
        if img_id:
            old_id = fks['ref_cover_img_id']
            db_set_reference_images(ref_id,
                                    cover_img_id=img_id,
                                    thumbnail_img_id=fks['ref_thumbnail_img_id'])
            if old_id:
                old_key = db_delete_reference_image(old_id)
                if old_key:
                    delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Cover image updated.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.my_edit_ref', ref_id=ref_id))


@bp.post('/my/<int:ref_id>/upload-thumbnail')
@login_required
def my_upload_thumbnail(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks or fks['usr_id'] != g.user_id:
        abort(404)
    try:
        img_id, _key = _upload_ref_image(ref_id, 'thumbnail')
        if img_id:
            old_id = fks['ref_thumbnail_img_id']
            db_set_reference_images(ref_id,
                                    cover_img_id=fks['ref_cover_img_id'],
                                    thumbnail_img_id=img_id)
            if old_id and old_id != fks['ref_cover_img_id']:
                old_key = db_delete_reference_image(old_id)
                if old_key:
                    delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Thumbnail image updated.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.my_edit_ref', ref_id=ref_id))


# =============================================================================
# ADMIN — COVER / THUMBNAIL IMAGE UPLOAD
# =============================================================================

_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
_IMAGE_EXT = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}


def _upload_ref_image(ref_id, slot):
    """Upload cover or thumbnail for a reference. slot is 'cover' or 'thumbnail'.
    Returns (img_id, s3_key) on success, raises on error."""
    f = request.files.get('image')
    if not f or not f.filename:
        flash(_('No file selected.'), 'warning')
        return None, None
    content_type = f.content_type or ''
    if content_type not in _ALLOWED_IMAGE_TYPES:
        flash(_('Only JPEG, PNG, and WebP images are accepted.'), 'warning')
        return None, None

    data = f.read()
    ext  = _IMAGE_EXT[content_type]
    s3_key = f'refs/{ref_id}/{slot}.{ext}'
    upload_bytes_to_s3(data, s3_key, _REF_IMAGES_BUCKET_NAME, content_type)
    img_id = db_create_reference_image(
        filename=f.filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=len(data),
    )
    return img_id, s3_key


@bp.post('/admin/<int:ref_id>/upload-cover')
@admin_required
def admin_upload_cover(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)
    try:
        img_id, _key = _upload_ref_image(ref_id, 'cover')
        if img_id:
            old_id = fks['ref_cover_img_id']
            db_set_reference_images(ref_id,
                                    cover_img_id=img_id,
                                    thumbnail_img_id=fks['ref_thumbnail_img_id'])
            if old_id:
                old_key = db_delete_reference_image(old_id)
                if old_key:
                    delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Cover image updated.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_edit_ref', ref_id=ref_id))


@bp.post('/admin/<int:ref_id>/upload-thumbnail')
@admin_required
def admin_upload_thumbnail(ref_id):
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)
    try:
        img_id, _key = _upload_ref_image(ref_id, 'thumbnail')
        if img_id:
            old_id = fks['ref_thumbnail_img_id']
            db_set_reference_images(ref_id,
                                    cover_img_id=fks['ref_cover_img_id'],
                                    thumbnail_img_id=img_id)
            if old_id and old_id != fks['ref_cover_img_id']:
                old_key = db_delete_reference_image(old_id)
                if old_key:
                    delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Thumbnail image updated.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_edit_ref', ref_id=ref_id))


@bp.post('/admin/<int:ref_id>/delete-image/<slot>')
@admin_required
def admin_delete_image(ref_id, slot):
    if slot not in ('cover', 'thumbnail'):
        abort(404)
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)
    try:
        img_id = fks['ref_cover_img_id'] if slot == 'cover' else fks['ref_thumbnail_img_id']
        if img_id:
            new_cover = None if slot == 'cover' else fks['ref_cover_img_id']
            new_thumb = None if slot == 'thumbnail' else fks['ref_thumbnail_img_id']
            db_set_reference_images(ref_id, cover_img_id=new_cover, thumbnail_img_id=new_thumb)
            old_key = db_delete_reference_image(img_id)
            if old_key:
                delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
            flash(_('Image removed.'), 'success')
    except Exception as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_edit_ref', ref_id=ref_id))


# =============================================================================
# COVER MANAGEMENT  (login_required + admin or owner)
# =============================================================================

def _check_ref_cover_access(ref_id):
    """Return fks dict if current user is admin or the reference owner. Abort otherwise."""
    fks = db_get_reference_fks(ref_id)
    if not fks:
        abort(404)
    if not (getattr(g, 'usr_is_admin', False) or fks['usr_id'] == g.user_id):
        abort(403)
    return fks


def _save_cover_from_upload(ref_id, fks):
    """Receive one uploaded image, generate cover (≤1200px) + thumb (200px),
    upload both to S3, create DB rows, replace any existing cover/thumb."""
    f = request.files.get('image')
    if not f or not f.filename:
        raise ValueError(_('No file selected.'))

    img = Image.open(BytesIO(f.read())).convert('RGB')

    # Cover: cap width at 1200px
    if img.width > 1200:
        img = img.resize((1200, int(img.height * 1200 / img.width)), Image.LANCZOS)
    cover_buf = BytesIO()
    img.save(cover_buf, format='JPEG', quality=85)
    cover_data = cover_buf.getvalue()

    # Thumb: 200px wide
    thumb = img.resize((200, int(img.height * 200 / img.width)), Image.LANCZOS)
    thumb_buf = BytesIO()
    thumb.save(thumb_buf, format='JPEG', quality=75)
    thumb_data = thumb_buf.getvalue()

    cover_key = f'refs/{ref_id}/cover.jpg'
    thumb_key = f'refs/{ref_id}/thumb.jpg'
    upload_bytes_to_s3(cover_data, cover_key, _REF_IMAGES_BUCKET_NAME, 'image/jpeg')
    upload_bytes_to_s3(thumb_data, thumb_key, _REF_IMAGES_BUCKET_NAME, 'image/jpeg')

    cover_img_id = db_create_reference_image(
        f'cover_{ref_id}.jpg', cover_key, 'image/jpeg', len(cover_data))
    thumb_img_id = db_create_reference_image(
        f'thumb_{ref_id}.jpg', thumb_key, 'image/jpeg', len(thumb_data))

    db_set_reference_images(ref_id, cover_img_id, thumb_img_id)

    # Delete old DB rows and S3 files (key may differ from new key)
    old_cover_id = fks.get('ref_cover_img_id')
    old_thumb_id = fks.get('ref_thumbnail_img_id')
    if old_cover_id:
        old_key = db_delete_reference_image(old_cover_id)
        if old_key:
            delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
    if old_thumb_id and old_thumb_id != old_cover_id:
        old_key = db_delete_reference_image(old_thumb_id)
        if old_key:
            delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)


def _save_thumbnail_from_upload(ref_id, fks):
    """Receive one uploaded image, resize to 200px wide, upload as thumb only."""
    f = request.files.get('image')
    if not f or not f.filename:
        raise ValueError(_('No file selected.'))

    img = Image.open(BytesIO(f.read())).convert('RGB')
    thumb = img.resize((200, int(img.height * 200 / img.width)), Image.LANCZOS)
    thumb_buf = BytesIO()
    thumb.save(thumb_buf, format='JPEG', quality=75)
    thumb_data = thumb_buf.getvalue()

    thumb_key    = f'refs/{ref_id}/thumb.jpg'
    upload_bytes_to_s3(thumb_data, thumb_key, _REF_IMAGES_BUCKET_NAME, 'image/jpeg')
    thumb_img_id = db_create_reference_image(
        f'thumb_{ref_id}.jpg', thumb_key, 'image/jpeg', len(thumb_data))

    old_thumb_id = fks.get('ref_thumbnail_img_id')
    db_set_reference_images(ref_id,
                            cover_img_id=fks.get('ref_cover_img_id'),
                            thumbnail_img_id=thumb_img_id)
    if old_thumb_id and old_thumb_id != fks.get('ref_cover_img_id'):
        old_key = db_delete_reference_image(old_thumb_id)
        if old_key:
            delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)


@bp.route('/<int:ref_id>/cover')
@login_required
def ref_cover_page(ref_id):
    fks = _check_ref_cover_access(ref_id)
    ref = db_get_reference(ref_id)
    raw_next = request.args.get('next', '')
    back_url = raw_next if raw_next.startswith('/') else url_for('bl_references.ref_detail', ref_id=ref_id)
    return render_template('references/ref_cover.html',
                           mc={}, ref=ref, fks=fks,
                           back_url=back_url,
                           images_bucket_url=_REF_IMAGES_BUCKET_URL,
                           upload_url=url_for('bl_references.ref_cover_upload', ref_id=ref_id),
                           upload_thumb_url=url_for('bl_references.ref_cover_upload_thumb', ref_id=ref_id),
                           delete_url=url_for('bl_references.ref_cover_delete', ref_id=ref_id))


@bp.post('/<int:ref_id>/cover/upload')
@login_required
def ref_cover_upload(ref_id):
    fks = _check_ref_cover_access(ref_id)
    try:
        _save_cover_from_upload(ref_id, fks)
        flash(_('Cover saved.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.ref_cover_page', ref_id=ref_id))


@bp.post('/<int:ref_id>/cover/upload-thumb')
@login_required
def ref_cover_upload_thumb(ref_id):
    fks = _check_ref_cover_access(ref_id)
    try:
        _save_thumbnail_from_upload(ref_id, fks)
        flash(_('Thumbnail saved.'), 'success')
    except Exception as e:
        flash(_('Upload failed: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.ref_cover_page', ref_id=ref_id))


@bp.post('/<int:ref_id>/cover/delete')
@login_required
def ref_cover_delete(ref_id):
    fks = _check_ref_cover_access(ref_id)
    raw_next = request.form.get('next', '')
    back_url = raw_next if raw_next.startswith('/') else url_for('bl_references.ref_detail', ref_id=ref_id)
    try:
        old_cover_id = fks.get('ref_cover_img_id')
        old_thumb_id = fks.get('ref_thumbnail_img_id')
        db_set_reference_images(ref_id, None, None)
        for img_id in {old_cover_id, old_thumb_id} - {None}:
            old_key = db_delete_reference_image(img_id)
            if old_key:
                delete_file_from_s3(old_key, _REF_IMAGES_BUCKET_NAME)
        flash(_('Cover removed.'), 'success')
    except Exception as e:
        flash(_('Error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.ref_cover_page', ref_id=ref_id,
                            **({'next': back_url} if back_url != url_for('bl_references.ref_detail', ref_id=ref_id) else {})))


# =============================================================================
# ADMIN — PERSONS
# =============================================================================

@bp.route('/admin/persons')
@admin_required
def admin_persons():
    q            = (request.args.get('q') or '').strip()
    needs_enrich = request.args.get('needs_enrich') == '1'
    rows = db_list_persons(q=q or None, needs_enrich=needs_enrich)
    return render_template('admin/references/persons.html',
                           mc={'admin': 'active'}, rows=rows, q=q,
                           needs_enrich=needs_enrich)


@bp.route('/admin/persons/new', methods=['GET', 'POST'])
@admin_required
def admin_new_person():
    if request.method == 'POST':
        try:
            db_create_person(
                firstname=_str('per_firstname'),
                familyname=_str('per_familyname'),
                caption_ita=_str('per_caption_ita'),
                caption_eng=_str('per_caption_eng'),
                strings=_str('per_strings'),
                won_nobel=_str('per_won_nobel'),
            )
            flash(_('Person created.'), 'success')
            return redirect(url_for('bl_references.admin_persons'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/references/person_form.html',
                           mc={'admin': 'active'}, row=None,
                           action=url_for('bl_references.admin_new_person'))


@bp.post('/admin/persons/<int:per_id>/enrich')
@admin_required
def admin_enrich_person(per_id):
    from .ai_provider import generate_person_captions, fetch_nobel_string
    row = db_get_person(per_id)
    if not row:
        abort(404)

    back_url = request.form.get('next') or url_for('bl_references.admin_persons')

    # Nobel lookup — always refresh from the authoritative API
    nobel_str = fetch_nobel_string(row['per_firstname'] or '', row['per_familyname'] or '')

    # Caption generation — only for fields that are currently empty
    new_ita = row.get('per_caption_ita') or ''
    new_eng = row.get('per_caption_eng') or ''
    captions_attempted = not new_ita or not new_eng
    captions_generated = False
    if captions_attempted:
        result = generate_person_captions(
            firstname=row['per_firstname'],
            familyname=row['per_familyname'],
        )
        if result['caption_ita'] or result['caption_eng']:
            if not new_ita:
                new_ita = result['caption_ita']
            if not new_eng:
                new_eng = result['caption_eng']
            captions_generated = True
        else:
            # AI returned nothing — mark as n.a. to stop repeated attempts
            if not new_ita:
                new_ita = 'n.a.'
            if not new_eng:
                new_eng = 'n.a.'

    db_update_person(
        per_id=per_id,
        firstname=row['per_firstname'],
        familyname=row['per_familyname'],
        caption_ita=new_ita or None,
        caption_eng=new_eng or None,
        strings=row.get('per_strings'),
        won_nobel=nobel_str if nobel_str is not None else row.get('per_won_nobel'),
    )

    msgs = []
    if captions_generated:
        msgs.append(_('Captions generated — please review.'))
    if nobel_str is not None:
        msgs.append(_('Nobel Prize data updated.'))
    if msgs:
        for m in msgs:
            flash(m, 'success')
        return redirect(url_for('bl_references.admin_edit_person', per_id=per_id))
    elif captions_attempted:
        # We tried but AI returned nothing
        flash(_('Could not generate captions for %(name)s.',
                name=f"{row['per_firstname']} {row['per_familyname']}"), 'warning')
        return redirect(back_url)
    else:
        # Captions already existed, not a Nobel laureate — nothing new to report
        flash(_('No new data found.'), 'info')
        return redirect(back_url)


@bp.route('/admin/persons/<int:per_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_person(per_id):
    row = db_get_person(per_id)
    if not row:
        abort(404)
    if request.method == 'POST':
        try:
            db_update_person(
                per_id=per_id,
                firstname=_str('per_firstname'),
                familyname=_str('per_familyname'),
                caption_ita=_str('per_caption_ita'),
                caption_eng=_str('per_caption_eng'),
                strings=_str('per_strings'),
                won_nobel=_str('per_won_nobel'),
            )
            flash(_('Person updated.'), 'success')
            return redirect(url_for('bl_references.admin_persons'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    outstanding = db_list_outstanding_works_by_person(per_id)
    return render_template('admin/references/person_form.html',
                           mc={'admin': 'active'}, row=row,
                           outstanding=outstanding,
                           action=url_for('bl_references.admin_edit_person', per_id=per_id))


@bp.post('/admin/persons/<int:per_id>/outstanding/add')
@admin_required
def admin_add_outstanding_work(per_id):
    if not db_get_person(per_id):
        abort(404)
    rtp_id = _int('rtp_id') or 4
    title = _str('title')
    year = _str('year')
    link = _str('link')
    if not title:
        flash(_('Title is required.'), 'danger')
        return redirect(url_for('bl_references.admin_edit_person', per_id=per_id))
    try:
        db_create_outstanding_work(per_id=per_id, rtp_id=rtp_id,
                                   usr_id=g.user_id, title=title, year=year, link=link)
        flash(_('Outstanding work added.'), 'success')
    except psycopg2.Error as e:
        flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_edit_person', per_id=per_id))


@bp.post('/admin/persons/<int:per_id>/outstanding/<int:ref_id>/delete')
@admin_required
def admin_delete_outstanding_work(per_id, ref_id):
    try:
        s3_keys = db_delete_reference(ref_id)
        for key in (s3_keys.get('cover_s3_key'), s3_keys.get('thumbnail_s3_key')):
            if key:
                delete_file_from_s3(key, _REF_IMAGES_BUCKET_NAME)
        flash(_('Outstanding work removed.'), 'success')
    except psycopg2.Error as e:
        flash(_('Cannot delete: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_edit_person', per_id=per_id))


@bp.post('/admin/persons/<int:per_id>/delete')
@admin_required
def admin_delete_person(per_id):
    try:
        db_delete_person(per_id)
        flash(_('Person deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Cannot delete person (still in use): %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_persons'))


# =============================================================================
# ADMIN — PUBLISHERS
# =============================================================================

@bp.route('/admin/publishers')
@admin_required
def admin_publishers():
    q    = (request.args.get('q') or '').strip()
    rows = db_list_publishers(q=q or None)
    return render_template('admin/references/publishers.html',
                           mc={'admin': 'active'}, rows=rows, q=q)


@bp.route('/admin/publishers/new', methods=['GET', 'POST'])
@admin_required
def admin_new_publisher():
    if request.method == 'POST':
        try:
            db_create_publisher(
                name=_str('pub_name') or '',
                othername=_str('pub_othername'),
                location=_str('pub_location'),
                description=_str('pub_description'),
            )
            flash(_('Publisher created.'), 'success')
            return redirect(url_for('bl_references.admin_publishers'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/references/publisher_form.html',
                           mc={'admin': 'active'}, row=None,
                           action=url_for('bl_references.admin_new_publisher'))


@bp.route('/admin/publishers/<int:pub_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_publisher(pub_id):
    row = db_get_publisher(pub_id)
    if not row:
        abort(404)
    if request.method == 'POST':
        try:
            db_update_publisher(
                pub_id=pub_id,
                name=_str('pub_name') or '',
                othername=_str('pub_othername'),
                location=_str('pub_location'),
                description=_str('pub_description'),
            )
            flash(_('Publisher updated.'), 'success')
            return redirect(url_for('bl_references.admin_publishers'))
        except psycopg2.Error as e:
            flash(_('Database error: %(msg)s', msg=str(e)), 'danger')
    return render_template('admin/references/publisher_form.html',
                           mc={'admin': 'active'}, row=row,
                           action=url_for('bl_references.admin_edit_publisher', pub_id=pub_id))


@bp.post('/admin/publishers/<int:pub_id>/delete')
@admin_required
def admin_delete_publisher(pub_id):
    try:
        db_delete_publisher(pub_id)
        flash(_('Publisher deleted.'), 'success')
    except psycopg2.Error as e:
        flash(_('Cannot delete publisher: %(msg)s', msg=str(e)), 'danger')
    return redirect(url_for('bl_references.admin_publishers'))
