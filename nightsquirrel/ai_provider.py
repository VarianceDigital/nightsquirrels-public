# nightsquirrel/ai_provider.py
import json
import logging
import os

log = logging.getLogger(__name__)

_STRICTNESS_GUIDANCE = {
    "high": (
        "HIGH strictness applies to this question type.\n"
        "Require: an exact task statement, all data needed to solve it, and readable input.\n"
        "Set is_quotable=false if: the core problem is missing, essential data is absent, "
        "or the statement is so incomplete a tutor cannot start without guessing the whole question."
    ),
    "medium": (
        "MEDIUM strictness applies to this question type.\n"
        "Require: a clear topic and an understandable goal or scope.\n"
        "Set is_quotable=false ONLY if: the topic is entirely absent or the request is incomprehensible.\n"
        "Acceptable even if details, sources, length, or format are unspecified — the tutor will ask."
    ),
    "low": (
        "LOW strictness applies to this question type.\n"
        "Require: a recognizable theme and a sense of the intended deliverable.\n"
        "Set is_quotable=false ONLY if: the submission is empty, pure nonsense, or completely off-topic.\n"
        "Exploratory and open-ended requests are always quotable at this level."
    ),
}


def extract_image_to_delta(image_bytes: bytes, media_type: str = 'image/jpeg') -> dict | None:
    """Use Claude vision to extract text and math formulas from an image.

    Returns a dict with:
      - 'delta': Quill delta dict ready to be JSON-serialised and stored
      - 'confidence': float 0-1 (1 = crisp printed text, 0 = unreadable)
    Returns None on any failure (fail-open).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("extract_image_to_delta: ANTHROPIC_API_KEY not set, skipping")
        return None

    try:
        import anthropic
        import base64
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = """You are a math and text OCR assistant for an Italian academic tutoring platform.
Extract the full content of the image and return it as structured segments.

Return ONLY valid JSON with exactly this structure:
{
  "segments": [
    {"type": "text",    "content": "..."},
    {"type": "formula", "latex":   "..."}
  ],
  "confidence": 0.0
}

Rules:
- Split content into text and formula segments as needed (interleaved is fine).
- For mathematical expressions use standard LaTeX compatible with KaTeX.
  Examples: \\frac{a}{b}  \\sqrt{x}  \\int_0^1 f(x)\\,dx  x^2 + y^2 = r^2
- Keep text in the original language (Italian, English, etc.).
- If the image contains only plain text with no math, return a single text segment.
- confidence: 1.0 = crisp digital/printed, 0.7 = clean handwriting, 0.4 = messy, 0.1 = nearly unreadable.

Display style rules (\\displaystyle):
- If a formula appears as a STANDALONE / BLOCK equation in the original image (on its own line,
  centred, or clearly separated from surrounding text), prefix its LaTeX with \\displaystyle followed
  by a space. Example: {"type": "formula", "latex": "\\\\displaystyle \\\\frac{x^2+1}{x-3} = 0"}
- If a formula is INLINE (embedded within a line of running text), do NOT add \\displaystyle,
  UNLESS it contains constructs that collapse badly without it (\\frac, \\int, \\sum, \\prod, \\lim
  with subscripts/superscripts) — in that case add \\displaystyle even inline.
- Simple inline expressions (t^3, \\sin(t), x=5, a+b) never need \\displaystyle.

- Return ONLY valid JSON, no markdown fences, no extra commentary."""

        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": "Extract all text and mathematical formulas from this image."},
                ],
            }],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        result = json.loads(raw)

        # Convert segments → Quill delta ops
        ops = []
        for seg in result.get("segments", []):
            if seg.get("type") == "text" and seg.get("content"):
                ops.append({"insert": seg["content"]})
            elif seg.get("type") == "formula" and seg.get("latex"):
                ops.append({"insert": {"formula": seg["latex"]}})

        if not ops:
            return None

        # Quill delta must end with a newline text insert
        last = ops[-1]
        if not (isinstance(last.get("insert"), str) and last["insert"].endswith("\n")):
            ops.append({"insert": "\n"})

        log.info("extract_image_to_delta: %d ops, confidence=%.2f",
                 len(ops), float(result.get("confidence", 0)))

        # Build readable plaintext for the sustainability gate:
        # text segments are used as-is; formula segments become [formula: ...]
        # so the gate knows math is present even when the editor was left empty.
        plaintext_parts = []
        for seg in result.get("segments", []):
            if seg.get("type") == "text" and seg.get("content"):
                plaintext_parts.append(seg["content"].strip())
            elif seg.get("type") == "formula" and seg.get("latex"):
                plaintext_parts.append(f"[formula: {seg['latex']}]")
        plaintext = " ".join(p for p in plaintext_parts if p)

        return {
            "delta":      {"ops": ops},
            "plaintext":  plaintext,
            "confidence": float(result.get("confidence", 0.5)),
        }

    except Exception:
        log.exception("extract_image_to_delta failed")
        return None


def analyze_question(
    title: str,
    plaintext: str,
    question_type_name: str,
    valid_subject_ids: list,
    valid_school_type_ids: list,
    subject_name: str | None = None,
    school_type_name: str | None = None,
    grade: int | None = None,
    difficulty: int | None = None,
    strictness_level: str = "medium",
) -> dict | None:
    """Call Claude to analyze a student question.

    Returns the parsed JSON analysis dict, or None on any failure.
    Fail-open: callers should proceed to normal quoting when None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("analyze_question: ANTHROPIC_API_KEY not set, skipping AI analysis")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        strictness_rules = _STRICTNESS_GUIDANCE.get(strictness_level, _STRICTNESS_GUIDANCE["medium"])

        system_prompt = f"""You are an academic question analyzer for an Italian tutoring platform.
You receive a student's question and must return a JSON object with two sections.

1. "input_suitability" — gate check:
   - "is_quotable" (bool): true if a tutor can make a meaningful start on this work.
   - "issues" (list): each with "code" (string) and "detail" (string). Possible codes:
     incomplete_statement, blurry_image, nonsensical_text, too_vague, off_topic, multiple_unrelated_questions.
     Empty list if no issues.
   - "student_hint" (string): a short, friendly message in Italian telling the student what to fix.
     Empty string if no issues.

2. "semantic_analysis" — classification:
   - "predicted_subject_id" (int): one of {json.dumps(valid_subject_ids)}
   - "predicted_school_type_id" (int): one of {json.dumps(valid_school_type_ids)}
   - "predicted_grade" (int or null): estimated school year (1-5), null if unclear
   - "predicted_pedagogical_difficulty" (int 1-5): how hard the concept is for the student
   - "predicted_resolution_complexity" (int 1-5): how much work the tutor needs
   - "confidence" (float 0-1): your confidence in the semantic analysis
   - "extracted_text" (string): cleaned/normalized version of the question text

GATE RULES:
{strictness_rules}

NEVER set is_quotable=false because the student has not listed specific names, dates, or sources,
is asking where to start, describes herself as a beginner, or has not specified length or format.
When in doubt, set is_quotable=true.

Return ONLY valid JSON, no markdown fences, no extra text."""

        meta_lines = []
        if subject_name:
            meta_lines.append(f"Subject: {subject_name}")
        if school_type_name:
            meta_lines.append(f"School type: {school_type_name}")
        if grade:
            meta_lines.append(f"Grade: {grade}")
        if difficulty:
            meta_lines.append(f"Difficulty (student-estimated): {difficulty}")
        meta_block = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

        user_msg = f"""Question title: {title}
Question type: {question_type_name}{meta_block}

Question content:
{plaintext or '(empty)'}"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text.strip()
        log.info("analyze_question: stop_reason=%s, raw length=%d", response.stop_reason, len(raw))

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        return json.loads(raw)

    except Exception:
        log.exception("analyze_question: AI call failed")
        return None


def analyze_question_with_vision(
    title: str,
    content_blocks: list,
    question_type_name: str,
    valid_subject_ids: list,
    valid_school_type_ids: list,
    subject_name: str | None = None,
    school_type_name: str | None = None,
    grade: int | None = None,
    difficulty: int | None = None,
    strictness_level: str = "medium",
) -> dict | None:
    """Like analyze_question but accepts multi-block content (text + inline images from the editor).

    content_blocks is a list of Claude content block dicts:
      {"type": "text", "text": "..."}  or
      {"type": "image", "source": {"type": "url", "url": "..."}}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("analyze_question_with_vision: ANTHROPIC_API_KEY not set, skipping")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        strictness_rules = _STRICTNESS_GUIDANCE.get(strictness_level, _STRICTNESS_GUIDANCE["medium"])

        system_prompt = f"""You are an academic question analyzer for an Italian tutoring platform.
You receive a student's question and must return a JSON object with two sections.

1. "input_suitability" — gate check:
   - "is_quotable" (bool): true if a tutor can make a meaningful start on this work.
   - "issues" (list): each with "code" (string) and "detail" (string). Possible codes:
     incomplete_statement, blurry_image, nonsensical_text, too_vague, off_topic, multiple_unrelated_questions.
     Empty list if no issues.
   - "student_hint" (string): a short, friendly message in Italian telling the student what to fix.
     Empty string if no issues.

2. "semantic_analysis" — classification:
   - "predicted_subject_id" (int): one of {json.dumps(valid_subject_ids)}
   - "predicted_school_type_id" (int): one of {json.dumps(valid_school_type_ids)}
   - "predicted_grade" (int or null): estimated school year (1-5), null if unclear
   - "predicted_pedagogical_difficulty" (int 1-5): how hard the concept is for the student
   - "predicted_resolution_complexity" (int 1-5): how much work the tutor needs
   - "confidence" (float 0-1): your confidence in the semantic analysis
   - "extracted_text" (string): cleaned/normalized version of the question text

GATE RULES:
{strictness_rules}

NEVER set is_quotable=false because the student has not listed specific names, dates, or sources,
is asking where to start, describes herself as a beginner, or has not specified length or format.
When in doubt, set is_quotable=true.

Return ONLY valid JSON, no markdown fences, no extra text."""

        meta_lines = []
        if subject_name:
            meta_lines.append(f"Subject: {subject_name}")
        if school_type_name:
            meta_lines.append(f"School type: {school_type_name}")
        if grade:
            meta_lines.append(f"Grade: {grade}")
        if difficulty:
            meta_lines.append(f"Difficulty (student-estimated): {difficulty}")
        meta_block = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

        intro = {"type": "text",
                 "text": f"Question title: {title}\nQuestion type: {question_type_name}{meta_block}\n\nQuestion content:"}
        user_content = [intro] + content_blocks

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = response.content[0].text.strip()
        log.info("analyze_question_with_vision: stop_reason=%s, raw length=%d",
                 response.stop_reason, len(raw))

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        return json.loads(raw)

    except Exception:
        log.exception("analyze_question_with_vision: AI call failed")
        return None


_NOBEL_CATEGORY_IT = {
    'Physics':                'Fisica',
    'Chemistry':              'Chimica',
    'Physiology or Medicine': 'Fisiologia o Medicina',
    'Literature':             'Letteratura',
    'Peace':                  'Pace',
    'Economic Sciences':      'Scienze Economiche',
}


def _fetch_nobel_prizes(firstname: str, familyname: str) -> list[dict]:
    """Query Nobel Prize API v2.1 for a person.
    Returns list of {year, category_en, category_it, motivation_en} or []."""
    import requests as _req
    if not familyname:
        return []
    try:
        r = _req.get(
            'https://api.nobelprize.org/2.1/laureates',
            params={'name': familyname, 'format': 'json'},
            timeout=5,
            headers={'User-Agent': 'NightSquirrels/1.0 (nightsquirrels.com)'},
        )
        if r.status_code != 200:
            log.debug("Nobel API: status %s for '%s'", r.status_code, familyname)
            return []
        laureates = r.json().get('laureates', [])
        if not laureates:
            return []
        # Match by first name — all firstname tokens must appear in the
        # laureate's name tokens (handles "Richard", "Richard H.", etc.)
        fn_lower  = (firstname or '').lower().strip()
        fn_tokens = set(fn_lower.split())
        matched   = None
        if fn_tokens:
            for lau in laureates:
                full = (lau.get('knownName', {}).get('en', '') or
                        lau.get('fullName',  {}).get('en', '') or '').lower()
                if fn_tokens.issubset(set(full.split())):
                    matched = lau
                    break
        else:
            # No first name available — accept sole result as best guess
            if len(laureates) == 1:
                matched = laureates[0]
        if matched is None:
            return []
        prizes = []
        for p in matched.get('nobelPrizes', []):
            cat_en = p.get('category', {}).get('en', '')
            prizes.append({
                'year':         p.get('awardYear', ''),
                'category_en':  cat_en,
                'category_it':  _NOBEL_CATEGORY_IT.get(cat_en, cat_en),
                'motivation_en': (p.get('motivation', {}) or {}).get('en', ''),
            })
        return prizes
    except Exception as e:
        log.debug("Nobel API error for '%s %s': %s", firstname, familyname, e)
        return []


def fetch_nobel_string(firstname: str, familyname: str) -> str | None:
    """Return a formatted Nobel Prize string for a person, or None if not a laureate.
    Format: "1921 - Physics" or "1921 - Physics; 1943 - Chemistry" for multiple prizes.
    """
    prizes = _fetch_nobel_prizes(firstname, familyname)
    if not prizes:
        return None
    return '; '.join(f"{p['year']} - {p['category_en']}" for p in prizes)


def generate_person_captions(firstname: str, familyname: str) -> dict:
    """Generate Italian and English short bios for a person.

    1. Tries Wikipedia (it + en) for factual grounding.
    2. Passes the extracts to Claude to format in the desired style.
    3. Falls back to Claude's own knowledge if Wikipedia finds nothing.

    Returns: {'caption_ita': str, 'caption_eng': str}
             Either value may be '' if generation failed.
    """
    import requests as _req

    full_name = f"{firstname or ''} {familyname or ''}".strip()

    def _wiki_extract(lang: str) -> str:
        try:
            r = _req.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{full_name.replace(' ', '_')}",
                timeout=5,
                headers={"User-Agent": "NightSquirrels/1.0 (nightsquirrels.com)"}
            )
            log.debug("Wikipedia %s for '%s': status=%s", lang, full_name, r.status_code)
            if r.status_code == 200:
                return r.json().get("extract", "")
        except Exception as e:
            log.debug("Wikipedia %s for '%s': exception %s", lang, full_name, e)
        return ""

    wiki_ita = _wiki_extract("it")
    wiki_eng = _wiki_extract("en")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("generate_person_captions: ANTHROPIC_API_KEY not set")
        return {"caption_ita": "", "caption_eng": ""}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Persona: {full_name}

Wikipedia (italiano): {wiki_ita or 'non trovato'}
Wikipedia (english):  {wiki_eng or 'not found'}

Genera due brevi didascalie biografiche per questa persona, una in italiano e una in inglese.
Lo stile deve essere: (luogo di nascita, data di nascita – luogo di morte, data di morte) \
seguita da una frase breve che dice chi era (se deceduta) o chi è (se ancora in vita).
Usa il tempo PASSATO ("È stato/È stata") solo per persone decedute.
Usa il tempo PRESENTE ("È un/È una") per persone ancora in vita.
Esempio persona deceduta — italiano: (Vienna, 26 aprile 1889 – Cambridge, 29 aprile 1951) È stato un filosofo \
e logico austriaco, considerato uno dei massimi pensatori del XX secolo.
Esempio persona deceduta — inglese: (Vienna, 26 April 1889 – Cambridge, 29 April 1951) Austrian philosopher \
and logician, widely regarded as one of the greatest thinkers of the 20th century.
Esempio persona in vita — italiano: (Londra, 12 marzo 1960) È un economista britannico, \
noto per i suoi studi sulla disuguaglianza globale.
Esempio persona in vita — inglese: (London, 12 March 1960) British economist, \
known for his research on global inequality.
Se la persona è ancora in vita, ometti la data di morte.
Se non hai informazioni sufficienti, restituisci una stringa vuota per quella lingua.
Rispondi SOLO con JSON valido, nessun altro testo:
{{"caption_ita": "...", "caption_eng": "..."}}"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        result = json.loads(raw)
        return {
            "caption_ita": result.get("caption_ita", ""),
            "caption_eng": result.get("caption_eng", ""),
        }
    except Exception as e:
        log.exception("generate_person_captions failed for %s: %s", full_name, e)
        return {"caption_ita": "", "caption_eng": ""}
