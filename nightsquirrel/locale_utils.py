from flask import session, request


def get_locale():
    lang = session.get('lang')
    if lang in ('it', 'en'):
        return lang
    return request.accept_languages.best_match(['it', 'en'], default='it')
