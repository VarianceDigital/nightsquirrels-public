import os

from flask import Flask
from flask_login import LoginManager
from flask_babel import Babel, lazy_gettext as _l

from .jinjafilters import *
from .errorhandlers import *
from .locale_utils import get_locale

login_manager = LoginManager()
login_manager.login_view = 'bl_auth.login'          # name of your login view
login_manager.login_message_category = 'warning'
login_manager.login_message = _l('Please log in to access this page.')

def create_app():
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ['SESSION_SECRET'],
        BABEL_DEFAULT_LOCALE='it',
        BABEL_DEFAULT_TIMEZONE='Europe/Rome',
        LANGUAGES=['it', 'en'],
    )

    #ADDS HANDLER TO CLOSE DATABASE AT END OF SESSION!
    from . import db
    db.init_app(app)

    # Flask-Login
    login_manager.init_app(app)

    # Flask-Babel
    Babel(app, locale_selector=get_locale)

    # Expose ticket state constants to all templates
    from .states import (TKT_NEW, TKT_NEEDS_CLARIFICATION, TKT_QUOTED,
                         TKT_NEEDS_REVIEW, TKT_REJECTED,
                         TKT_ACCEPTED, TKT_ASSIGNED, TKT_IN_PROGRESS,
                         TKT_DELIVERED_PENDING_PAYMENT, TKT_DELIVERED,
                         TKT_CLOSED, TKT_CANCELLED,
                         QUESTION_EDITABLE_STATES, ALL_STATES)

    @app.context_processor
    def inject_ticket_states():
        return dict(
            TKT_NEW=TKT_NEW,
            TKT_NEEDS_CLARIFICATION=TKT_NEEDS_CLARIFICATION,
            TKT_QUOTED=TKT_QUOTED,
            TKT_NEEDS_REVIEW=TKT_NEEDS_REVIEW,
            TKT_REJECTED=TKT_REJECTED,
            TKT_ACCEPTED=TKT_ACCEPTED,
            TKT_ASSIGNED=TKT_ASSIGNED,
            TKT_IN_PROGRESS=TKT_IN_PROGRESS,
            TKT_DELIVERED_PENDING_PAYMENT=TKT_DELIVERED_PENDING_PAYMENT,
            TKT_DELIVERED=TKT_DELIVERED,
            TKT_CLOSED=TKT_CLOSED,
            TKT_CANCELLED=TKT_CANCELLED,
            QUESTION_EDITABLE_STATES=QUESTION_EDITABLE_STATES,
            ALL_STATES=ALL_STATES,
        )

    # user_loader must be defined *after* app + DB
    from .db_auth import db_get_user_by_id
    from .user_model import User

    @login_manager.user_loader
    def load_user(user_id: str):
        # Flask-Login gives you a string; convert to int if needed
        try:
            usr_id = int(user_id)
        except (TypeError, ValueError):
            return None

        row = db_get_user_by_id(usr_id)
        if row is None:
            return None
        return User.from_db_row(row)


    from . import bl_home
    app.register_blueprint(bl_home.bp)

    from . import bl_auth
    app.register_blueprint(bl_auth.bp)

    from . import bl_email_confirm
    from . import bl_question
    app.register_blueprint(bl_email_confirm.bp)
    app.register_blueprint(bl_question.bp)

    #Add other blueprints if needed

    from . import auth
    app.register_blueprint(auth.bp)

    from . import bl_admin
    app.register_blueprint(bl_admin.bp)

    from .bl_tutor import bp as bl_tutor_bp
    app.register_blueprint(bl_tutor_bp)

    from .bl_pusher import bp as bl_pusher_bp
    app.register_blueprint(bl_pusher_bp)

    from . import bl_payer
    app.register_blueprint(bl_payer.bp)

    from . import bl_lang
    app.register_blueprint(bl_lang.bp)

    from . import bl_references
    app.register_blueprint(bl_references.bp)

    from . import bl_tags
    app.register_blueprint(bl_tags.bp)

    from . import bl_examples
    app.register_blueprint(bl_examples.bp)

    from . import bl_ideas
    app.register_blueprint(bl_ideas.bp)

    #ADDS HANDLER FOR ERRORs
    app.register_error_handler(500, error_500)
    app.register_error_handler(404, error_404)

    #JINJA FILTERS
    app.jinja_env.filters['slugify'] = slugify
    app.jinja_env.filters['displayError'] = displayError
    app.jinja_env.filters['tkt_state_label'] = tkt_state_label
    app.jinja_env.filters['tkt_state_badge'] = tkt_state_badge
    app.jinja_env.filters['localized_name'] = localized_name

    return app