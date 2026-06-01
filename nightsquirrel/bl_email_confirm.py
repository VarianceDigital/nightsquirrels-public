from flask import (
    Blueprint, url_for, flash, redirect
)
from flask_login import login_user
from flask_babel import gettext as _

from .user_model import User

from .layoutUtils import *
from .db_auth import *
import os


bp = Blueprint('bl_email_confirm', __name__)


@bp.route('/emailconfirmationhtml/<email_link_token>')
def emailconfirmationhtml(email_link_token):

    error, usr_id = db_check_email_link_token(email_link_token, os.environ["JWT_SECRET_HTML"])
    if error==0:
        user_row = db_get_user_data(usr_id)
        db_set_user_confirmed(user_row)
        user_row['usr_confirmed'] = True
        user = User.from_db_row(user_row)
        login_user(user)
        flash(_('Your email is confirmed, have fun'))
    else:
        flash(_('Problems with your confirmation email'))
    
    return redirect(url_for('bl_home.index'))
 
