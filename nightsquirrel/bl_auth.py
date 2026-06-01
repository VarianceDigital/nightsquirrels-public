from flask import (
    Blueprint, render_template, url_for, flash, redirect, request, g
)

from flask_login import login_required, login_user, logout_user, current_user
from flask_babel import gettext as _
import jwt

from .user_model import User

from .auth import manage_cookie_policy
from .db_auth import (
    db_check_user, db_update_user, db_delete_account, db_get_user_data,
    create_random_access_key,db_create_custom_name,db_create_custom_tile,
    db_create_user_entry, create_email_link_token, validate_sign_up, 
    ext_send_email, db_check_if_email_exists, db_get_user_by_id,
    db_check_username,db_update_user_name, check_valid_key,db_update_user_key,
    create_numeric_otp,db_save_otp_for_user_with_email,db_check_otp, db_reset_user_otp,
    db_update_student_academic_profile,
)
from .db_lookup import db_get_schooltypes
from .layoutUtils import read_data_from_form, set_menu
from .s3_operations import delete_file_from_s3, write_tile_to_s3
from .db_payment import db_get_active_payer_link, db_get_default_payment_method
import os

bp = Blueprint('bl_auth', __name__, url_prefix='/auth')

@bp.route('/signup',methods=('GET', 'POST'))
@manage_cookie_policy
def signup():
    mc = set_menu("signup")
    error = 0
    if request.method == 'POST':
        if 'btn_signup' in request.form:
            form_data = read_data_from_form()
            error = validate_sign_up(form_data)
            if error == 101:
                flash(_("Invalid email"))
            elif error == 102:
                flash(_("Email already used for a subscription"))
            elif error == 0:
                email = form_data['email']
                access_key = create_random_access_key()
                custom_name, custom_color = db_create_custom_name()
                tile_filename,tile_text = db_create_custom_tile(custom_color)
                new_id = db_create_user_entry(form_data['email'], access_key, custom_name, tile_filename)
                #CREATE A FILE ON S3 WITH THE TILES SVG TEXT AND FILENAME
                write_tile_to_s3(tile_filename,os.environ["AWS_TILES_BUCKET_NAME"],tile_text)    
                
                #Prepare data for confirmation email
                email_link_token = create_email_link_token(new_id, email, os.environ["JWT_SECRET_HTML"])
                
                #Send confirmaton email with visible access key
                ext_send_email(email, access_key,
                               os.environ["BASE_URL"] + '/emailconfirmationhtml/',
                               'emailservice-ntsqr','signup',
                               email_link_token)

                #Promote user to logged!
                # Log the user in via Flask-Login (unconfirmed, but authenticated)
                user_row = db_get_user_by_id(new_id)
                user = User.from_db_row(user_row)
                login_user(user)
            
                #Notify user!
                flash(_("Welcome to Night Squirrels!"))
                flash(_("We sent you an email containing a link: please click the link and confirm your subscription."))
                flash(_("We assigned you a nickname: %(name)s; you can change it in your profile.", name=custom_name))
                flash(_("We created you a profile icon — hope you like it!")) 

                return redirect(url_for('bl_home.index'))

    return render_template('auth/signup_frm.html', mc=mc, error=error)
 

@bp.route('/login',methods=('GET', 'POST'))
@manage_cookie_policy
def login():
    mc = set_menu("login")
    if request.method == 'POST':
        if 'btn_unlock' in request.form:
            form_data = read_data_from_form()
            user_row = db_check_user(form_data)
            if user_row is None:
                logout_user()
                flash(_("Could not login!"))
            else:
                user_obj = User.from_db_row(user_row)
                login_user(user_obj) # Flask-login
                flash(_("You are logged in :)")) 
                return redirect(url_for('bl_home.index'))

    return render_template('auth/login_frm.html', mc=mc)


@bp.route('/logout')
@manage_cookie_policy
def logout():
    logout_user()
    flash(_("See you soon!")) 
    return redirect(url_for('bl_home.index'))


@bp.route('/userprofile',methods=('GET', 'POST'))
@login_required
@manage_cookie_policy
def userprofile():
    error = 0
    
    mc = set_menu("userprofile")
    if request.method == 'POST':
        
        if 'btn_save_username'  in request.form:
            form_data = read_data_from_form()
            user_name = form_data['username']
            error = db_check_username(user_name)
            if error == 120:
                flash(_("User name too short"))
            elif error == 121:
                flash(_("User name too logn"))
            elif error == 122:
                flash(_("User name already in use"))
            else:
                db_update_user_name(g.user_id, user_name)
                #MUST UPATE GLOBAL
                g.user_name = user_name
                flash(_("User name updated!"))
        elif 'btn_changeaccesskey'  in request.form:
            form_data = read_data_from_form()
            confirm_access_key = form_data['confirmaccesskey']
            new_access_key = form_data['newaccesskey']
            current_access_key = form_data['accesskey']
            if new_access_key!=confirm_access_key:
                error = 106
            elif db_check_user({'email':g.user_email, 'key':current_access_key}) is None:
                #"recycling" check_user
                error = 105
            else:
                error = check_valid_key(new_access_key)
                if error == 0:
                    db_update_user_key(g.user_id, new_access_key)
                    flash(_("Access key updated!"))
                else:
                    error = 107 #errors 108, 109, 110 -> 107

        elif 'btn_save_email' in request.form:
            form_data = read_data_from_form()

            error = validate_sign_up(form_data)
            if error == 101:
                flash(_("Invalid email"))
            elif error == 102:
                flash(_("Email already used for a subscription"))
            elif error == 0:
                email = form_data['email']
                access_key = create_random_access_key()
                db_update_user(g.user_id, email, access_key)
                
                #Prepare data for confirmation email
                email_link_token = create_email_link_token(g.user_id, email, os.environ["JWT_SECRET_HTML"])
                
                #Send confirmaton email with visible access key
                ext_send_email(email, access_key, os.environ["BASE_URL"] + '/emailconfirmationhtml/', 'emailservice-ntsqr','change', email_link_token)

                #Notify user!
                flash(_("Your email has been updated."))
                flash(_("We sent you a new email containing a link: please click the link and confirm your change."))
                flash(_("WARNING: your access key has been changed!")) 

                return redirect(url_for('bl_home.index'))

        elif 'btn_save_academic' in request.form:
            form_data = read_data_from_form()
            new_sct_id = None
            new_grade = None
            try:
                new_sct_id = int(form_data.get('sct_id')) if form_data.get('sct_id') else None
            except (ValueError, TypeError):
                pass
            try:
                new_grade = int(form_data.get('usr_school_grade')) if form_data.get('usr_school_grade') else None
            except (ValueError, TypeError):
                pass
            db_update_student_academic_profile(g.user_id, new_sct_id, new_grade)
            g.sct_id = new_sct_id
            g.usr_school_grade = new_grade
            flash(_("Academic profile updated!"))

    record = db_get_user_data(g.user_id)
    s3tileurl = os.environ["AWS_TILES_BUCKET_URL"]
    schooltypes = db_get_schooltypes()

    # Payment info for profile page
    payer_link = db_get_active_payer_link(g.user_id) if g.usr_is_student else None
    is_self_pay = payer_link and payer_link['payer_usr_id'] == g.user_id
    if g.usr_is_payer:
        pmt = db_get_default_payment_method(g.user_id)
    elif payer_link:
        pmt = db_get_default_payment_method(payer_link['payer_usr_id'])
    else:
        pmt = None

    return render_template('auth/profile.html',
                           mc=mc, s3tileurl=s3tileurl, record=record, error=error,
                           payer_link=payer_link, pmt=pmt, is_self_pay=is_self_pay,
                           schooltypes=schooltypes)


@bp.route('/forgotkey',methods=('GET', 'POST'))
@manage_cookie_policy
def forgotkey():

    mc = set_menu("forgotkey")
    error = 0    

    if request.method == 'POST':
        if 'btn_send_new_key' in request.form:
            form_data = read_data_from_form()
            email = form_data['email']
            nice_error = db_check_if_email_exists(email)
            if nice_error==102:
                #EMAIL EXISTS! IT'S WHAT WE WANT

                #Prepare data for "reset key" email

                otp = create_numeric_otp()
                usr_id = db_save_otp_for_user_with_email(email, otp)
                #db_save_otp_for_user_with_email returns the user id having "email" as email address

                email_link_token = create_email_link_token(usr_id, email, os.environ["JWT_SECRET_HTML"])
                
                #Send "reset key" email - SENDING OTP instead of access key
                ext_send_email(email, otp, 'email-link-not-used', 'emailservice-ntsqr','resetkey', email_link_token)

                #Notify user!
                flash(_("We sent you an email. Use the OTP code inside to reset your access key.")) 
                return redirect(url_for('bl_auth.resetkey',token=email_link_token ))
            else:
                flash(_("Email not found"))

    return render_template('auth/forgot_frm.html', mc=mc, error = error)


@bp.route('/resetkey/<token>',methods=('GET', 'POST'))
@manage_cookie_policy
def resetkey(token):

    #SECURITY CHECK: DECODE OTP PASSED TO ENDPOINT
    try:
        decoded = jwt.decode(token, os.environ["JWT_SECRET_HTML"], algorithms=['HS256'])
        usr_id = decoded['usr_id']
    except jwt.DecodeError:
        return redirect(url_for('bl_home.index'))

    mc = set_menu("resetkey")
    error = 0    

    if request.method == 'POST':
        if 'btn_resetaccesskey' in request.form:            
            form_data = read_data_from_form()
            otp = form_data['otp']
            new_access_key = form_data['newaccesskey']
            confirm_access_key = form_data['confirmaccesskey']
            error = db_check_otp(usr_id, otp) #may give error 111
            if error==0:
                if new_access_key!=confirm_access_key:
                    error = 106
                else:
                    error = check_valid_key(new_access_key)
                    if error == 0:
                        db_update_user_key(usr_id, new_access_key)
                        db_reset_user_otp(usr_id)
                        flash(_("Access key updated!"))
                        flash(_("Use your new access key to login"))
                        return redirect(url_for('bl_home.index'))
                    else:
                        error = 107 #errors 108, 109, 110 -> 107    

    return render_template('auth/resetkey_frm.html', mc=mc, error = error)


@bp.route('/deleteaccount')
@login_required
def deleteaccount():
    
    tile_to_be_removed= db_delete_account(g.user_id)
    logout_user()
    
    delete_file_from_s3(tile_to_be_removed, os.environ["AWS_TILES_BUCKET_NAME"])

    flash(_("Account deleted"))

    return redirect(url_for('bl_home.index'))


@bp.route('/_whoami')
@login_required
def _whoami():
    return {
        "user_id": g.user_id,
        "email": g.user_email,
        "g_admin": getattr(g, "usr_is_admin", None),
        "cu_admin": getattr(current_user, "usr_is_admin", None),
        "g_tutor": getattr(g, "usr_is_tutor", None),
        "cu_tutor": getattr(current_user, "usr_is_tutor", None),
    }