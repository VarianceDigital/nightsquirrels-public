from flask import Blueprint, session, request, redirect, make_response

bp = Blueprint('bl_lang', __name__)


@bp.route('/set-language/<lang>')
def set_language(lang):
    if lang not in ('it', 'en'):
        lang = 'it'
    session['lang'] = lang
    resp = make_response(redirect(request.referrer or '/'))
    resp.set_cookie('lang', lang, max_age=60 * 60 * 24 * 365)
    return resp
