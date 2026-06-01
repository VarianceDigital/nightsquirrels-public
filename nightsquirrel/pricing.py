# nightsquirrel/pricing.py
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
import copy
import hashlib
import itertools
import json
import math

# ---------- CONFIG (tune these) ----------
GRADE_POINTS_IT = {
    "medie": 0,
    "biennio": 1,
    "triennio": 2,
    "maturita_preuni": 3,
}

SUBJECT_POINTS = {
    "other": 0, "italian": 0,
    "english": 1, "history": 1, "geography": 1,
    "philosophy": 1, "music": 1,
    "math": 2, "cs": 2, "ai": 2,
    "physics": 3, "chemistry": 3,
}

TASK_POINTS = {
    "single_exercise": 0,
    "exercise_set":    1,
    "explain_concept": 1,
    "show_steps":      1,
    "summary_schema":  2,
    "essay":           2,
    "project":         3,
}

MEDIA_POINTS = {
    "text": 0,
    "text_video": 1,
    "text_video_diagram": 2,
}

# point range -> EUR band (inclusive)
PRICE_BANDS_EUR = [
    ((0, 2),   (3, 4)),
    ((3, 5),   (4, 6)),
    ((6, 8),   (6, 8)),
    ((9, 11),  (8, 10)),
    ((12, 15), (10, 14)),
    # >=16 => overflow/custom
]

DEFAULT_CURRENCY = "EUR"
DEFAULT_UNKNOWN_SUBJECT_POINTS = 1
MARKET_FACTOR = 2.5       # Global scale lever — tune without migration
QUOTE_VERSION = "qv1"


@dataclass(frozen=True)
class QuoteInput:
    grade_level: str
    subject: str
    task_type: str
    length_band: int      # 0..4
    difficulty: int        # 1..5
    media: str
    batch: Optional[str] = None  # 'similar_5_20' | 'similar_20_plus' | 'mixed' | None


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def compute_points(q: QuoteInput) -> Tuple[int, bool]:
    pts = 0
    pts += GRADE_POINTS_IT.get(q.grade_level, 1)
    pts += SUBJECT_POINTS.get(q.subject, DEFAULT_UNKNOWN_SUBJECT_POINTS)
    pts += TASK_POINTS.get(q.task_type, 1)
    pts += _clamp(q.length_band, 0, 4)
    pts += _clamp(q.difficulty, 1, 5)
    pts += MEDIA_POINTS.get(q.media, 0)

    if q.batch == "similar_5_20":
        pts -= 1
    elif q.batch == "similar_20_plus":
        pts -= 2
    elif q.batch == "mixed":
        pts += 1

    overflow = (pts >= 16) or (q.length_band >= 4)
    return pts, overflow


def price_band(points: int) -> Optional[Tuple[int, int]]:
    for (lo_hi, band) in PRICE_BANDS_EUR:
        lo, hi = lo_hi
        if lo <= points <= hi:
            return band
    return None


# ---------- Layer A: score breakdown + base price ----------

PRICING_RULES = {
    "combine_rule": "additive_over_base",
    "rounding": {"mode": "to_nearest_50_cents", "min_cents": 500},
}


def _round_price(cents: int) -> int:
    """Round to nearest 50 cents, enforce minimum."""
    return max(round(cents / 50) * 50, PRICING_RULES["rounding"]["min_cents"])


def compute_score_breakdown(q: QuoteInput) -> dict:
    """Structured score output for transparency."""
    return {
        "grade":     GRADE_POINTS_IT.get(q.grade_level, 1),
        "subject":   SUBJECT_POINTS.get(q.subject, DEFAULT_UNKNOWN_SUBJECT_POINTS),
        "task_type": TASK_POINTS.get(q.task_type, 1),
        "length":    _clamp(q.length_band, 0, 4),
        "difficulty": _clamp(q.difficulty, 1, 5),
        "media":     MEDIA_POINTS.get(q.media, 0),
    }


def compute_base_price(score_total: int) -> Optional[int]:
    """Score -> single base_price_cents.

    Interpolates within the matching band, then scales by MARKET_FACTOR.
    Returns None if overflow (no band found).
    """
    for (pts_range, eur_range) in PRICE_BANDS_EUR:
        pts_lo, pts_hi = pts_range
        eur_lo, eur_hi = eur_range
        if pts_lo <= score_total <= pts_hi:
            span = pts_hi - pts_lo
            t = (score_total - pts_lo) / span if span else 0
            base_eur = eur_lo + t * (eur_hi - eur_lo)
            return _round_price(round(base_eur * 100 * MARKET_FACTOR))
    return None


# ---------- Layer B: axes catalog + offer builder ----------

AXES_CATALOG = [
    {
        "id": "speed",
        "label": "Delivery speed",
        "default_value_id": "std",
        "values": [
            {"id": "std",  "rank": 0, "label": "Standard", "delivery_hours": 24,
             "multiplier_bp": 10000, "hint": "Good value"},
            {"id": "fast", "rank": 1, "label": "Fast", "delivery_hours": 8,
             "multiplier_bp": 12500, "hint": "For deadlines"},
        ],
    },
    {
        "id": "depth",
        "label": "Explanation depth",
        "default_value_id": "basic",
        "values": [
            {"id": "basic",   "rank": 0, "label": "Essential", "multiplier_bp": 10000,
             "features": ["Step-by-step solution", "Final answer highlighted"]},
            {"id": "guided",  "rank": 1, "label": "Guided", "multiplier_bp": 12000,
             "features": ["Everything in Essential", "Key concept explanations",
                          "Common-mistake warnings"]},
            {"id": "mastery", "rank": 2, "label": "Mastery", "multiplier_bp": 14000,
             "features": ["Everything in Guided", "Worked similar example",
                          "Study tips & further reading"]},
        ],
    },
]

_BADGE_RULES = {
    ("std", "basic"):    ["Best value"],
    ("std", "guided"):   ["Popular"],
    ("fast", "mastery"): ["Premium"],
}


def _badges_for(axes_values: dict) -> list:
    key = (axes_values.get("speed", ""), axes_values.get("depth", ""))
    return list(_BADGE_RULES.get(key, []))


def _compute_option_price_additive(base_cents: int, multipliers_bp: List[int]) -> int:
    """Additive-over-base: final = base * (10000 + sum(m_i - 10000)) / 10000."""
    addon_bp = sum(m - 10000 for m in multipliers_bp)
    raw = base_cents * (10000 + addon_bp) / 10000
    return _round_price(int(raw))


def build_offer_payload(quote_input: dict) -> dict:
    """Layer B: Build full multi-axis payload from quote_input dict.

    Returns the qv1 payload structure with axes, options (cartesian product),
    pricing rules, and UI hints.
    """
    q = QuoteInput(**{k: v for k, v in quote_input.items() if k != 'batch'},
                   batch=quote_input.get('batch'))
    pts, overflow = compute_points(q)
    score_breakdown = compute_score_breakdown(q)
    base_price = compute_base_price(pts)

    if overflow or base_price is None:
        return {
            "quote_version": QUOTE_VERSION,
            "currency": DEFAULT_CURRENCY,
            "score": {"total": pts, "breakdown": score_breakdown},
            "base_price_cents": None,
            "axes": [],
            "pricing": PRICING_RULES,
            "options": [],
            "overflow": True,
            "ui": {"layout": "needs_review"},
        }

    axes = copy.deepcopy(AXES_CATALOG)

    # Build cartesian product of axis values
    axis_value_lists = [
        [(axis["id"], v) for v in axis["values"]]
        for axis in axes
    ]

    options = []
    default_option_id = None

    for combo in itertools.product(*axis_value_lists):
        axes_map = {}
        multipliers = []
        labels = []
        delivery_hours = None
        features = None

        for axis_id, val in combo:
            axes_map[axis_id] = val["id"]
            multipliers.append(val["multiplier_bp"])
            labels.append(val["label"])
            if "delivery_hours" in val:
                delivery_hours = val["delivery_hours"]
            if "features" in val:
                features = val["features"]

        # Composite ID: opt_speed_std__depth_basic
        id_parts = [f"{axis_id}_{val_id}" for axis_id, val_id in axes_map.items()]
        option_id = "opt_" + "__".join(id_parts)

        price_cents = _compute_option_price_additive(base_price, multipliers)

        option = {
            "id": option_id,
            "axes": axes_map,
            "price_cents": price_cents,
            "label": " \u00b7 ".join(labels),
            "badges": _badges_for(axes_map),
        }
        if delivery_hours is not None:
            option["delivery_hours"] = delivery_hours
        if features is not None:
            option["features"] = features

        options.append(option)

        # Default = all axes at their default values
        is_default = all(
            axes_map[ax["id"]] == ax["default_value_id"] for ax in axes
        )
        if is_default:
            default_option_id = option_id

    return {
        "quote_version": QUOTE_VERSION,
        "currency": DEFAULT_CURRENCY,
        "score": {"total": pts, "breakdown": score_breakdown},
        "base_price_cents": base_price,
        "axes": axes,
        "pricing": PRICING_RULES,
        "options": options,
        "overflow": False,
        "ui": {
            "layout": "sliders_plus_cards",
            "default_selected_option_id": default_option_id,
            "copy": {
                "headline": "Choose your plan",
                "subheadline": "Adjust speed and depth to fit your needs. "
                               "You only pay if you accept.",
            },
        },
    }


# ---------- ID-to-key mappings (DB lookup IDs -> pricing keys) ----------

# tbl_q_subject.sbj_id -> SUBJECT_POINTS key
_SBJ_ID_MAP = {
    0: "other",       # Altro
    1: "math",        # Matematica
    2: "italian",     # Italiano/Letteratura
    3: "english",     # Inglese
    4: "physics",     # Fisica
    5: "philosophy",  # Filosofia
    6: "cs",          # Informatica
    7: "music",       # Musica
    8: "ai",          # Intelligenza artificiale
}

# tbl_q_question_type.qtp_id -> TASK_POINTS key
_QTP_ID_MAP = {
    1: "single_exercise",  # Esercizio singolo
    2: "exercise_set",     # Serie di esercizi
    3: "explain_concept",  # Spiegazione di concetto
    4: "show_steps",       # Passaggi / dimostrazione
    5: "summary_schema",   # Riassunto / schema / mappa
    6: "summary_schema",   # Timeline (same pricing, distinct ID)
    7: "essay",            # Tema / elaborato scritto
    8: "project",          # Progetto / presentazione
}

# tbl_s_schooltype.sct_id -> GRADE_POINTS_IT key
_SCT_ID_BASE = {
    1: "medie",             # Scuola Primaria
    2: "medie",             # Scuola Media
    10: "maturita_preuni",  # Università
}

def _grade_level_for_liceo(grade: Optional[int]) -> str:
    """Map year within a 5-year liceo/istituto to pricing grade_level."""
    if grade is not None and grade >= 5:
        return "maturita_preuni"
    if grade is not None and grade >= 3:
        return "triennio"
    return "biennio"

def _resolve_grade_level(sct_id: Optional[int], grade: Optional[int]) -> str:
    if sct_id is None:
        return "biennio"
    if sct_id in _SCT_ID_BASE:
        return _SCT_ID_BASE[sct_id]
    return _grade_level_for_liceo(grade)


def quote_from_question_data(
    sbj_id: Optional[int],
    qtp_id: Optional[int],
    sct_id: Optional[int],
    grade: Optional[int],
    difficulty: Optional[int],
    plaintext: Optional[str],
) -> Dict[str, Any]:
    """Bridge between DB question metadata and the pricing engine."""
    q_input = build_quote_input(sbj_id, qtp_id, sct_id, grade, difficulty, plaintext)
    payload = build_offer_payload(q_input)

    return {
        "points": payload["score"]["total"],
        "overflow": payload["overflow"],
        "note": "Overflow/custom quote (scope too large or complex)." if payload["overflow"] else None,
        "version": QUOTE_VERSION,
        "quote_input": q_input,
        "quote_signature": compute_quote_signature(q_input),
        "quote_payload": payload,
    }


# ---------- helpers ----------

def length_band_from_text(text: str) -> int:
    words = len((text or "").split())
    if words <= 40:
        return 0
    if words <= 120:
        return 1
    if words <= 250:
        return 2
    if words <= 500:
        return 3
    return 4


def build_quote_input(
    sbj_id: Optional[int],
    qtp_id: Optional[int],
    sct_id: Optional[int],
    grade: Optional[int],
    difficulty: Optional[int],
    plaintext: Optional[str],
) -> dict:
    """Build a normalized dict of economic inputs for signature/payload computation."""
    return {
        "grade_level": _resolve_grade_level(sct_id, grade),
        "subject": _SBJ_ID_MAP.get(sbj_id, "italian"),
        "task_type": _QTP_ID_MAP.get(qtp_id, "single_ex"),
        "length_band": length_band_from_text(plaintext or ""),
        "difficulty": _clamp(difficulty or 1, 1, 5),
        "media": "text",
        "batch": None,
    }


def compute_quote_signature(quote_input: dict) -> str:
    """SHA-256 hex of canonicalized input dict."""
    canonical = json.dumps(quote_input, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()
