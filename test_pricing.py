"""
Pricing engine smoke test — run after DB rebase to verify Layer A + B.

Usage:  python3 test_pricing.py
"""
import sys
import os

# Ensure the project package is importable
sys.path.insert(0, os.path.dirname(__file__))

from nightsquirrel.pricing import (
    quote_from_question_data,
    build_quote_input,
    compute_quote_signature,
)

PASS = 0
FAIL = 0


def check(condition, label):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK]   {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


# ================================================================
# Phase 1 — Pricing engine smoke test (Layer A scores + Layer B offers)
# ================================================================
print("=" * 64)
print("PHASE 1: Pricing engine smoke test")
print("=" * 64)

cases = [
    # (sbj_id, qtp_id, sct_id, grade, difficulty, plaintext, label)
    (0, 1, 1, None, 1, "short question",
     "Minimal: altro, elementary, single_ex, diff=1"),
    (1, 1, 2, None, 1, "short question",
     "Easy/short math, scuola media, diff=1"),
    (3, 3, 8, 4, 3, "a " * 130,
     "Mid physics, liceo triennio, ~130 words, diff=3"),
    (1, 2, 8, 5, 4, "a " * 260,
     "Hard math, liceo maturita, ~260 words, diff=4"),
    (1, 4, 10, None, 5, "a " * 600,
     "Full essay, uni math, ~600 words, diff=5 -> overflow?"),
]

for sbj, qtp, sct, grade, diff, text, label in cases:
    r = quote_from_question_data(sbj, qtp, sct, grade, diff, text)
    p = r["quote_payload"]
    score = p["score"]["total"]
    bd = p["score"]["breakdown"]
    base = p.get("base_price_cents")
    overflow = p["overflow"]

    print(f"\n--- {label} ---")
    print(f"  score={score}  breakdown={bd}")
    print(f"  base_price_cents={base}  overflow={overflow}")

    if not overflow:
        check(base is not None, "base_price_cents is not None")
        check(base >= 500, f"base_price >= 500 (min floor), got {base}")

        options = p["options"]
        check(len(options) == 6,
              f"6 options (2 speed x 3 depth), got {len(options)}")

        # std/basic should equal base price (both multipliers = 10000)
        std_basic = [o for o in options
                     if o["axes"].get("speed") == "std"
                     and o["axes"].get("depth") == "basic"]
        if std_basic:
            check(std_basic[0]["price_cents"] == base,
                  f"std/basic == base ({std_basic[0]['price_cents']}c vs {base}c)")

        # fast/mastery should be the most expensive
        fast_mastery = [o for o in options
                        if o["axes"].get("speed") == "fast"
                        and o["axes"].get("depth") == "mastery"]
        if fast_mastery:
            max_price = max(o["price_cents"] for o in options)
            check(fast_mastery[0]["price_cents"] == max_price,
                  f"fast/mastery is most expensive ({fast_mastery[0]['price_cents']}c)")

        # Additive-over-base check for fast/mastery:
        # addon_bp = (12500-10000) + (14000-10000) = 6500
        # expected = base * (10000 + 6500) / 10000
        if fast_mastery and base:
            expected_raw = base * 16500 / 10000
            # _round_price rounds to nearest 50, min 500
            expected = max(round(expected_raw / 50) * 50, 500)
            check(fast_mastery[0]["price_cents"] == expected,
                  f"fast/mastery additive formula ({fast_mastery[0]['price_cents']}c vs {expected}c expected)")

        # Every option must have delivery_hours
        for o in options:
            check("delivery_hours" in o,
                  f"{o['id']} has delivery_hours")

        # Print all options for visual inspection
        for o in options:
            badges = o.get("badges", [])
            badge_str = f"  {badges}" if badges else ""
            print(f"    {o['id']:40s}  {o['price_cents']:>5d}c "
                  f"({o['price_cents']/100:.2f} EUR)  "
                  f"SLA {o.get('delivery_hours', '?')}h{badge_str}")
    else:
        check(base is None, "overflow -> base_price_cents is None")
        check(len(p["options"]) == 0, "overflow -> no options")
        print("  -> NEEDS_REVIEW (overflow)")


# ================================================================
# Phase 2 — Signature stability
# ================================================================
print()
print("=" * 64)
print("PHASE 2: Signature stability")
print("=" * 64)

# Same inputs -> same signature
a = build_quote_input(1, 2, 8, 3, 2, "some text here")
b = build_quote_input(1, 2, 8, 3, 2, "some text here")
sig_a = compute_quote_signature(a)
sig_b = compute_quote_signature(b)
check(sig_a == sig_b, f"identical inputs -> identical sig")

# Different difficulty -> different signature
c = build_quote_input(1, 2, 8, 3, 3, "some text here")
sig_c = compute_quote_signature(c)
check(sig_a != sig_c, "different difficulty -> different sig")

# Different subject -> different signature
d = build_quote_input(3, 2, 8, 3, 2, "some text here")
sig_d = compute_quote_signature(d)
check(sig_a != sig_d, "different subject -> different sig")

# Different text length band -> different signature
e = build_quote_input(1, 2, 8, 3, 2, "a " * 300)
sig_e = compute_quote_signature(e)
check(sig_a != sig_e, "different length band -> different sig")

# Same text, same band -> same signature
f = build_quote_input(1, 2, 8, 3, 2, "other short text")
sig_f = compute_quote_signature(f)
check(sig_a == sig_f,
      "different text but same length band -> same sig")


# ================================================================
# Phase 3 — Edge cases
# ================================================================
print()
print("=" * 64)
print("PHASE 3: Edge cases")
print("=" * 64)

# Unknown subject ID -> _SBJ_ID_MAP falls back to "italian" -> 0 points
r = quote_from_question_data(999, 1, 2, None, 1, "x")
check(not r["overflow"], "unknown sbj_id -> no overflow (fallback)")
check(r["quote_payload"]["score"]["breakdown"]["subject"] == 0,
      "unknown sbj_id -> falls back to 'italian' = 0 points")

# None difficulty -> clamped to 1
r = quote_from_question_data(0, 1, 1, None, None, "x")
check(r["quote_payload"]["score"]["breakdown"]["difficulty"] == 1,
      "None difficulty -> clamped to 1")

# Empty plaintext
r = quote_from_question_data(0, 1, 1, None, 1, "")
check(r["quote_payload"]["score"]["breakdown"]["length"] == 0,
      "empty text -> length_band = 0")

# None plaintext
r = quote_from_question_data(0, 1, 1, None, 1, None)
check(r["quote_payload"]["score"]["breakdown"]["length"] == 0,
      "None text -> length_band = 0")

# Rounding: all prices are multiples of 50
r = quote_from_question_data(1, 1, 2, None, 2, "hello world")
for o in r["quote_payload"]["options"]:
    check(o["price_cents"] % 50 == 0,
          f"{o['id']} price {o['price_cents']}c is multiple of 50")

# UI defaults
p = r["quote_payload"]
ui = p.get("ui", {})
check(ui.get("layout") == "sliders_plus_cards",
      "non-overflow layout = sliders_plus_cards")
check(ui.get("default_selected_option_id") is not None,
      "default_selected_option_id is set")
default_opt = ui.get("default_selected_option_id", "")
check(default_opt == "opt_speed_std__depth_basic",
      f"default option = std/basic, got {default_opt}")


# ================================================================
# Phase 4 — Monotonicity across all scores
# ================================================================
print()
print("=" * 64)
print("PHASE 4: Monotonicity (base price never drops as score increases)")
print("=" * 64)

from nightsquirrel.pricing import compute_base_price

prev_price = 0
all_monotonic = True
curve = []

for score in range(0, 16):
    bp = compute_base_price(score)
    curve.append((score, bp))
    if bp is not None:
        check(bp >= prev_price,
              f"score {score:2d}: {bp:5d}c ({bp/100:.2f} EUR) >= prev {prev_price}c")
        prev_price = bp

# Score 16+ should overflow (return None)
bp16 = compute_base_price(16)
check(bp16 is None, "score 16 -> overflow (None)")

print("\n  Full base price curve:")
for score, bp in curve:
    if bp is not None:
        print(f"    score {score:2d} -> {bp:5d}c ({bp/100:6.2f} EUR)")


# ================================================================
# Summary
# ================================================================
print()
print("=" * 64)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
if FAIL == 0:
    print("All checks passed.")
else:
    print("Some checks FAILED — review output above.")
print("=" * 64)

sys.exit(1 if FAIL else 0)
