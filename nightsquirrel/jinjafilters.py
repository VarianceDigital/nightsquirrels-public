from inflection import parameterize
from markupsafe import Markup
from flask import g
from flask_babel import gettext as _
from .states import (TKT_NEW, TKT_NEEDS_CLARIFICATION, TKT_QUOTED,
                     TKT_NEEDS_REVIEW, TKT_REJECTED,
                     TKT_ACCEPTED, TKT_ASSIGNED, TKT_IN_PROGRESS,
                     TKT_DELIVERED_PENDING_PAYMENT, TKT_DELIVERED,
                     TKT_CLOSED, TKT_CANCELLED)

def slugify(myvar):
    return parameterize(myvar)[:80].rstrip('-')

#This data would better go in a database...
errorDict = { 
    "Err1": "ERROR 1: watch out for error n.1!",
    "Err2": "ERROR 2: watch out for error n.2!",
    "Err9": "ERROR 9: watch out for error n.9!"
}

def displayError(errNum):
    key = "Err"+str(errNum)
    result = errorDict[key]
    return result


def _tkt_state_labels():
    return {
        TKT_NEW: _("New"),
        TKT_NEEDS_CLARIFICATION: _("Needs clarification"),
        TKT_QUOTED: _("Quoted"),
        TKT_NEEDS_REVIEW: _("Needs review"),
        TKT_REJECTED: _("Rejected"),
        TKT_ACCEPTED: _("Accepted"),
        TKT_ASSIGNED: _("Assigned"),
        TKT_IN_PROGRESS: _("In progress"),
        TKT_DELIVERED_PENDING_PAYMENT: _("Pending payment"),
        TKT_DELIVERED: _("Delivered"),
        TKT_CLOSED: _("Closed"),
        TKT_CANCELLED: _("Cancelled"),
    }

def tkt_state_label(state):
    return _tkt_state_labels().get(state, _("Unknown"))

_TKT_STATE_BADGES = {
    TKT_NEW:                      "text-bg-secondary",
    TKT_NEEDS_CLARIFICATION:      "text-bg-warning",
    TKT_QUOTED:                   "text-bg-info",
    TKT_NEEDS_REVIEW:             "text-bg-warning",
    TKT_REJECTED:                 "text-bg-danger",
    TKT_ACCEPTED:                 "text-bg-success",
    TKT_ASSIGNED:                 "text-bg-primary",
    TKT_IN_PROGRESS:              "text-bg-primary",
    TKT_DELIVERED_PENDING_PAYMENT: "text-bg-warning",
    TKT_DELIVERED:                "text-bg-success",
    TKT_CLOSED:                   "text-bg-secondary",
    TKT_CANCELLED:                "text-bg-danger",
}

def tkt_state_badge(state):
    label = _tkt_state_labels().get(state, _("Unknown"))
    css = _TKT_STATE_BADGES.get(state, "text-bg-secondary")
    return Markup(f'<span class="badge {css}">{label}</span>')


def localized_name(row, base_col):
    lang = getattr(g, 'lang', 'it')
    suffix = '_eng' if lang == 'en' else '_ita'
    return row.get(base_col + suffix, '')

