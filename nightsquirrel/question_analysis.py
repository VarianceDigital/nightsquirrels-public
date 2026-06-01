# nightsquirrel/question_analysis.py
import json
import logging
from .ai_provider import analyze_question, analyze_question_with_vision
from .db_lookup import db_get_subjects, db_get_schooltypes, db_get_questiontypes
from .db_ticket import db_save_ai_analysis
from .db_questions import db_update_question_ai_predictions

log = logging.getLogger(__name__)

_QTP_STRICTNESS = {
    1: "high",    # Esercizio singolo
    2: "high",    # Serie di esercizi
    3: "medium",  # Spiegazione di concetto
    4: "high",    # Passaggi / dimostrazione
    5: "medium",  # Riassunto / schema / mappa
    6: "medium",  # Timeline
    7: "medium",  # Tema / elaborato scritto
    8: "low",     # Progetto / presentazione
}


def delta_to_text_with_formulas(delta_json: str) -> str:
    """Walk Quill delta ops and build a text representation that preserves formulas.

    Text inserts are kept as-is. Formula embeds are rendered as LaTeX in brackets.
    E.g.: 'what is the value of [cos(\\pi)] ?'
    """
    try:
        delta = json.loads(delta_json) if isinstance(delta_json, str) else delta_json
        ops = delta.get('ops', []) if isinstance(delta, dict) else []
    except (json.JSONDecodeError, TypeError):
        return ''

    parts = []
    for op in ops:
        insert = op.get('insert', '')
        if isinstance(insert, str):
            parts.append(insert)
        elif isinstance(insert, dict) and 'formula' in insert:
            parts.append(f"[{insert['formula']}]")
    return ''.join(parts).strip()


def delta_to_content_blocks(delta_json: str) -> list:
    """Convert Quill delta to Claude content blocks for vision-aware analysis.

    Text inserts and formula embeds are collapsed into text blocks.
    Image embeds become image URL blocks.
    Returns a list of Claude content block dicts.
    """
    try:
        delta = json.loads(delta_json) if isinstance(delta_json, str) else delta_json
        ops = delta.get('ops', []) if isinstance(delta, dict) else []
    except (json.JSONDecodeError, TypeError):
        return []

    blocks = []
    text_buffer = []

    def flush():
        text = ''.join(text_buffer).strip()
        if text:
            blocks.append({"type": "text", "text": text})
        text_buffer.clear()

    for op in ops:
        insert = op.get('insert', '')
        if isinstance(insert, str):
            text_buffer.append(insert)
        elif isinstance(insert, dict):
            if 'formula' in insert:
                text_buffer.append(f"[{insert['formula']}]")
            elif 'image' in insert:
                flush()
                url = insert['image']
                if url and url.startswith('http'):
                    blocks.append({"type": "image",
                                   "source": {"type": "url", "url": url}})
    flush()
    return blocks


def analyze_and_gate_question(
    tkt_id: int,
    qtn_id: int,
    title: str,
    plaintext: str,
    ctx_delta_json: str,
    sbj_id,
    qtp_id,
    sct_id,
    grade,
    difficulty,
):
    """Run AI analysis on a submitted question.

    Returns (is_quotable: bool, student_hint: str|None, predictions: dict|None).
    predictions contains AI-predicted values for quoting (sbj_id, sct_id, grade, difficulty).
    Fail-open: returns (True, None, None) if AI is unavailable or fails.
    """
    try:
        # Resolve lookup IDs to human-readable names
        subjects = {r['sbj_id']: r for r in db_get_subjects()}
        schooltypes = {r['sct_id']: r for r in db_get_schooltypes()}
        qtypes = {r['qtp_id']: r for r in db_get_questiontypes()}

        qtp = qtypes.get(qtp_id)
        question_type_name = qtp['qtp_name_ita'] if qtp else 'Non specificato'
        strictness_level = _QTP_STRICTNESS.get(qtp_id, "medium")

        subj = subjects.get(sbj_id)
        subject_name = subj['sbj_name_ita'] if subj else None
        sct = schooltypes.get(sct_id)
        school_type_name = sct['sct_name_ita'] if sct else None

        valid_subject_ids = list(subjects.keys())
        valid_school_type_ids = list(schooltypes.keys())

        # Build content blocks from delta (Option C: vision-aware)
        content_blocks = delta_to_content_blocks(ctx_delta_json)
        has_images = any(b.get('type') == 'image' for b in content_blocks)

        if has_images and content_blocks:
            # Vision path: pass text + image blocks directly to Claude
            result = analyze_question_with_vision(
                title=title,
                content_blocks=content_blocks,
                question_type_name=question_type_name,
                valid_subject_ids=valid_subject_ids,
                valid_school_type_ids=valid_school_type_ids,
                subject_name=subject_name,
                school_type_name=school_type_name,
                grade=grade,
                difficulty=difficulty,
                strictness_level=strictness_level,
            )
        else:
            # Text-only path: enrich with formula LaTeX, fall back to plaintext
            enriched_text = delta_to_text_with_formulas(ctx_delta_json)
            ai_plaintext = enriched_text if enriched_text else plaintext
            result = analyze_question(
                title=title,
                plaintext=ai_plaintext,
                question_type_name=question_type_name,
                valid_subject_ids=valid_subject_ids,
                valid_school_type_ids=valid_school_type_ids,
                subject_name=subject_name,
                school_type_name=school_type_name,
                grade=grade,
                difficulty=difficulty,
                strictness_level=strictness_level,
            )

        if result is None:
            return (True, None, None)

        # Validate structure
        suitability = result.get('input_suitability')
        if not isinstance(suitability, dict):
            log.warning("analyze_and_gate_question: invalid input_suitability structure")
            return (True, None, None)

        # Store full analysis
        db_save_ai_analysis(tkt_id, result)

        is_quotable = suitability.get('is_quotable', True)
        student_hint = suitability.get('student_hint') or None

        # Extract predictions and save to question
        predictions = None
        semantic = result.get('semantic_analysis')
        if isinstance(semantic, dict) and qtn_id is not None:
            predictions = {
                'sbj_id': semantic.get('predicted_subject_id'),
                'sct_id': semantic.get('predicted_school_type_id'),
                'grade': semantic.get('predicted_grade'),
                'difficulty': semantic.get('predicted_resolution_complexity'),
            }
            if is_quotable:
                db_update_question_ai_predictions(
                    qtn_id=qtn_id,
                    sbj_id=predictions['sbj_id'],
                    sct_id=predictions['sct_id'],
                    grade=predictions['grade'],
                    difficulty=predictions['difficulty'],
                )

        return (is_quotable, student_hint, predictions)

    except Exception:
        log.exception("analyze_and_gate_question failed for ticket %s", tkt_id)
        return (True, None, None)
