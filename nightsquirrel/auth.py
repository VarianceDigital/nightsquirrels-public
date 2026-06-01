import functools
from flask import current_app
from flask import (
    Blueprint, g, redirect, request, session,flash, url_for, Response
)
from flask_login import current_user
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

import os
from .db_auth import *
from .user_model import User     # new import

bp = Blueprint('auth', __name__, url_prefix='/auth')

#IMPORTANT! Called for every request
@bp.before_app_request
def pre_operations(): 

    #ALL STATIC REQUESTS BYPASS!!!
    if request.endpoint == 'static':
        return

    #REDIRECT http -> https in HEROKU
    if 'DYNO' in os.environ:
        current_app.logger.critical("DYNO ENV !!!!")
        if request.url.startswith('http://'):
            url = request.url.replace('http://', 'https://', 1)
            code = 301
            return redirect(url, code=code)

    from flask_babel import get_locale
    g.lang = str(get_locale())

    g.policyCode = -1 #SET DEFAULT INDEPENDENTLY TO WRAPPER
    policyCode = session.get("cookie-policy")
    #possible values Null -> no info, 0 -> Strict, 1 -> Minimal, 
    #                                 2 -> Analisys, 3 -> All
    if policyCode !=None:
        g.policyCode = policyCode

    # MAP current_user -> g.* so old code/templates keep working
    if current_user.is_authenticated:
        g.user_is_logged = True
        g.user_confirmed = getattr(current_user, 'confirmed', False)
        g.user_email = getattr(current_user, 'email', '')
        g.user_name = getattr(current_user, 'name', '')

        # Role flags (used by business logic / admin blueprint)
        g.usr_is_student = bool(getattr(current_user, 'usr_is_student', False))
        g.usr_is_tutor   = bool(getattr(current_user, 'usr_is_tutor', False))
        g.usr_is_admin   = bool(getattr(current_user, 'usr_is_admin', False))
        g.usr_is_payer   = bool(getattr(current_user, 'usr_is_payer', False))
        g.usr_isvalid    = bool(getattr(current_user, 'is_valid', True))

        g.sct_id = getattr(current_user, 'sct_id', None)
        g.usr_school_grade = getattr(current_user, 'usr_school_grade', None)
        g.student_profile_complete = (
            g.usr_is_student
            and g.sct_id is not None
            and g.usr_school_grade is not None
        )

        try:
            g.user_id = int(current_user.id)
        except (TypeError, ValueError):
            g.user_id = None

        g.missing_token = False
        g.invalid_token = False
    else:
        g.user_is_logged = False
        g.user_confirmed = False
        g.user_email = ''
        g.user_name = ''

        g.usr_is_student = False
        g.usr_is_tutor = False
        g.usr_is_admin = False
        g.usr_is_payer = False
        g.usr_isvalid = False

        g.sct_id = None
        g.usr_school_grade = None
        g.student_profile_complete = False

        g.user_id = None
        g.missing_token = True
        g.invalid_token = False

#WRAPPER FOR COOKIE SETTINGS 
def manage_cookie_policy(view):

    @functools.wraps(view)
    def wrapped_view(**kwargs):

        g.showCookieAlert = False #DEFAULT
        if g.policyCode == -1:
            g.showCookieAlert = True

        return view(**kwargs)

    return wrapped_view


def confirmation_required(view):

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'confirmed', False):
            return redirect(url_for('bl_home.index'))
        return view(**kwargs)

    return wrapped_view


@bp.route('/ajcookiepolicy/',methods=('GET', 'POST'))
def ajcookiepolicy():
    #DECIDE COOKIE PREFERENCE STRATEGY
    if request.method == 'POST':
        data = request.json
        btn_name = data['btnselected']
        checkbox_analysis = data['checkboxAnalysis']
        checkbox_necessary = data['checkboxNecessary']
        if btn_name == 'btnAgreeAll':
            session['cookie-policy'] = 3
        elif btn_name == 'btnAgreeEssential':
            session['cookie-policy'] = 1
        elif btn_name == 'btnSaveCookieSettings':
            session['cookie-policy'] = 0 #default
            if checkbox_necessary and not checkbox_analysis:
                session['cookie-policy'] = 1
            elif checkbox_analysis and not checkbox_necessary:
                #never happends if main checkbox disabled!
                session['cookie-policy'] = 2
            elif checkbox_necessary and checkbox_analysis:
                session['cookie-policy'] = 3

    return Response(status=204)


def admin_required(view):
    """
    Requires a logged-in user with admin role.
    Uses g.usr_is_admin (set in before_app_request) but also falls back to current_user.
    """
    @wraps(view)
    @login_required
    def wrapped_view(**kwargs):
        is_admin = bool(getattr(g, "usr_is_admin", False)) or bool(getattr(current_user, "usr_is_admin", False))
        if not is_admin:
            # 403 Forbidden is semantically correct here
            abort(403)
        return view(**kwargs)
    return wrapped_view


def tutor_required(view):
    """
    Requires a logged-in user with tutor role.
    """
    @wraps(view)
    @login_required
    def wrapped_view(**kwargs):
        is_tutor = bool(getattr(g, "usr_is_tutor", False)) or bool(getattr(current_user, "usr_is_tutor", False))
        if not is_tutor:
            abort(403)
        return view(**kwargs)
    return wrapped_view


def payer_required(view):
    """
    Requires a logged-in user with payer role.
    """
    @wraps(view)
    @login_required
    def wrapped_view(**kwargs):
        is_payer = bool(getattr(g, "usr_is_payer", False)) or bool(getattr(current_user, "usr_is_payer", False))
        if not is_payer:
            abort(403)
        return view(**kwargs)
    return wrapped_view