from flask import (
    Blueprint, render_template, request, send_from_directory
)
from .layoutUtils import *
from .auth import *
from .db_payment import db_get_active_payer_link, db_get_default_payment_method
from .db_references import db_list_references
from .bl_references import _REF_IMAGES_BUCKET_URL

bp = Blueprint('bl_home', __name__)

@bp.route('/',methods=('GET', 'POST'))
@manage_cookie_policy
def index():
    
    record = db_get_user_data(g.user_id) #Can return None if user is not logged
    s3tileurl = os.environ["AWS_TILES_BUCKET_URL"]
    mc = set_menu("home") #to highlight menu option

    payment_ok = False
    if g.user_confirmed:
        payer_link = db_get_active_payer_link(g.user_id) if g.usr_is_student else None
        if g.usr_is_payer:
            pmt = db_get_default_payment_method(g.user_id)
        elif payer_link:
            pmt = db_get_default_payment_method(payer_link['payer_usr_id'])
        else:
            pmt = None
        payment_ok = pmt is not None and pmt.get('pmt_vault_status') == 'vaulted'

    _refs = db_list_references(library_only=True)
    library_preview = sorted(_refs, key=lambda r: (not r['ref_is_current'], not r['ref_is_recent']))[:6]

    return render_template('home/index.html', mc=mc,
                        record=record, s3tileurl=s3tileurl,
                        payment_ok=payment_ok,
                        library_preview=library_preview,
                        images_bucket_url=_REF_IMAGES_BUCKET_URL)


@bp.route('/about', methods=('GET', 'POST'))
@manage_cookie_policy
def about():

    mc = set_menu("about")
    return render_template('home/about.html', mc=mc)


@bp.route('/faq', methods=('GET', 'POST'))
@manage_cookie_policy
def faq():
    mc = set_menu("faq")
    return render_template('home/faq.html', mc=mc)


@bp.route('/privacy-notice',methods=('GET', 'POST'))
def privacy():

    mc = set_menu("")
    return render_template('home/privacy-notice.html', mc=mc)


@bp.route('/terms-of-service',methods=('GET', 'POST'))
def termsofservice():
    mc = set_menu("")
    return render_template('home/terms-of-service.html', mc=mc)


#MANAGE sitemap and robots calls 
#These files are usually in root, but for Flask projects must
#be in the static folder
@bp.route('/robots.txt')
@bp.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(current_app.static_folder, request.path[1:])

