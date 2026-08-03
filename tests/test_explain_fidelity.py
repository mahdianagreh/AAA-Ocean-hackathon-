"""/explain number-fidelity tests — the auditability guarantee.

Run: .venv/bin/python tests/test_explain_fidelity.py

THE CLAIM UNDER TEST: the phrasing layer never computes, rounds, or invents a
number. If 71.8 ever becomes "about 72", or "72%" becomes "roughly three-quarters",
these tests fail.

The check is a literal string match on the rendered number, not "some number
appears somewhere" — that weaker form would pass a paragraph that quietly swapped
one figure for another.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.rag import explain  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


DRIVERS = [
    {"feature": "rainfall_3h_mm", "value": 41.2, "contribution": 0.31},
    {"feature": "slope_mean", "value": 12.4, "contribution": 0.22},
    {"feature": "antecedent_index", "value": 0.63, "contribution": 0.18},
]


def _build(language="en", **kw):
    args = dict(
        catchment_id="AQ-C01", risk_level="high", language=language,
        shap_drivers=DRIVERS, plume_probability=0.72,
        arrival_window_hours=(8.0, 12.0), confidence="moderate",
        reef_zone_id="R-04", rainfall_percentile=99, catchment_label="Wadi Yutum",
    )
    args.update(kw)
    return explain.build_explanation(**args)


def test_every_number_appears_verbatim_both_languages():
    for lang in ("en", "ar"):
        text, nums = _build(lang)
        missing = explain.numbers_present(text, nums)
        check(f"[{lang}] every source number is verbatim in the text",
              not missing, f"missing {missing}")


def test_awkward_decimals_are_not_rounded():
    """The specific drift the risk register names: 71.8 must not become 72."""
    for prob, expected in [(0.718, "71.8"), (0.7183, "71.83"), (0.5, "50"),
                           (0.999, "99.9"), (0.0725, "7.25")]:
        text, nums = _build("en", plume_probability=prob)
        check(f"probability {prob} renders as '{expected}%' exactly",
              f"{expected}%" in text,
              f"text says: ...{text[text.find('probability') - 12:text.find('probability') + 20]}...")
        missing = explain.numbers_present(text, nums)
        check(f"  and fidelity holds for {prob}", not missing, f"missing {missing}")


def test_no_hedging_words_appear():
    """A number qualified by 'about' is no longer the number it was handed."""
    banned_en = ["about ", "approximately", "roughly", "around ", "~", "circa",
                 "nearly", "almost "]
    banned_ar = ["حوالي", "تقريبا", "تقريبًا", "نحو "]
    for lang, banned in (("en", banned_en), ("ar", banned_ar)):
        text, _ = _build(lang, plume_probability=0.718)
        found = [w for w in banned if w in text.lower()]
        check(f"[{lang}] no hedging language around numbers", not found,
              f"found {found}")


def test_arrival_window_endpoints_both_present():
    text, nums = _build("en", arrival_window_hours=(8.5, 12.25))
    check("both window endpoints appear", "8.5" in text and "12.25" in text,
          f"text: {text[-160:]}")
    check("window endpoints recorded in source_numbers",
          nums["arrival_start_hours"] == 8.5 and nums["arrival_end_hours"] == 12.25)


def test_numbers_identical_across_languages():
    """Language changes; facts do not."""
    _, en_nums = _build("en")
    _, ar_nums = _build("ar")
    check("source_numbers identical EN vs AR", en_nums == ar_nums,
          f"en={en_nums} ar={ar_nums}")


def test_fidelity_checker_actually_catches_a_violation():
    """A test that cannot fail is not a test. Prove the detector detects."""
    text, nums = _build("en")
    tampered = text.replace("72%", "about 72%")
    missing_ok = explain.numbers_present(text, nums)
    missing_bad = explain.numbers_present(tampered.replace("72", "72.4"), nums)
    check("clean text passes the checker", not missing_ok)
    check("tampered text is caught by the checker", bool(missing_bad),
          "detector missed an altered number")


def test_matches_the_calibration_example():
    """The paragraph from the task file, used as the shape we target."""
    text, _ = _build("en")
    for fragment in [
        "is classified as high risk because",
        "forecast 3-hour rainfall exceeds the catchment's historical 99th percentile",
        "the upstream terrain is steep",
        "antecedent soil conditions support rapid runoff",
        "72% probability of reaching Reef Zone R-04 within 8–12 hours",
        "Confidence is moderate because nearshore currents are represented by a "
        "coarse global model",
    ]:
        check(f"contains: {fragment[:52]}...", fragment in text,
              f"absent from: {text}")


def test_unknown_driver_is_shown_not_dropped():
    """A driver we cannot phrase is still a driver."""
    text, _ = _build("en", shap_drivers=[{"feature": "mystery_feature", "value": 1.0}])
    check("unknown feature name still surfaces", "mystery feature" in text,
          f"text: {text}")


def test_no_drivers_says_so():
    text, _ = _build("en", shap_drivers=[])
    check("empty driver list is stated, not silently omitted",
          "drivers were not supplied" in text, f"text: {text}")


if __name__ == "__main__":
    print("/explain number-fidelity tests\n")
    test_every_number_appears_verbatim_both_languages()
    test_awkward_decimals_are_not_rounded()
    test_no_hedging_words_appear()
    test_arrival_window_endpoints_both_present()
    test_numbers_identical_across_languages()
    test_fidelity_checker_actually_catches_a_violation()
    test_matches_the_calibration_example()
    test_unknown_driver_is_shown_not_dropped()
    test_no_drivers_says_so()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("number fidelity verified — the phrasing layer alters nothing")
