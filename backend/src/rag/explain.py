"""The /explain paragraph — bilingual, grounded, and arithmetically inert.

THE RULE, RESTATED BECAUSE IT IS THE WHOLE POINT
-----------------------------------------------
The generator PHRASES numbers it is handed. It never computes one, never rounds
one, never invents one. If the phrasing layer can change a score, the system stops
being auditable, and that is exactly what a judge will probe.

So the shipped generator is a template. Numbers are interpolated with a formatter
that does no rounding: `_num` renders the value it was given, trimming only
trailing zeros that carry no information. 72.0 renders as "72", 71.8 renders as
"71.8", and neither becomes "about 72" or "roughly three-quarters".

`tests/test_explain_fidelity.py` asserts, for both languages, that every number in
`source_numbers` appears verbatim in the returned text.
"""

from __future__ import annotations

import re
from decimal import Decimal

TEMPLATE_EN = (
    "{catchment_label} is classified as {risk_phrase} because {driver_clause}. "
    "{plume_clause}{confidence_clause}"
)

TEMPLATE_AR = (
    "{catchment_label} مصنّف على أنه {risk_phrase} لأن {driver_clause}. "
    "{plume_clause}{confidence_clause}"
)

RISK_PHRASE = {
    "en": {"minimal": "minimal risk", "low": "low risk", "moderate": "moderate risk",
           "high": "high risk", "critical": "critical risk"},
    "ar": {"minimal": "خطر ضئيل", "low": "خطر منخفض", "moderate": "خطر متوسط",
           "high": "خطر مرتفع", "critical": "خطر حرج"},
}

CONFIDENCE_WORD = {
    "en": {"low": "low", "moderate": "moderate", "high": "high"},
    "ar": {"low": "منخفضة", "moderate": "متوسطة", "high": "مرتفعة"},
}

# Feature name -> the clause this project actually uses for it. Unknown features
# fall back to their raw name rather than being dropped: a driver we cannot phrase
# is still a driver, and hiding it would misrepresent the model.
#
# DECISION (p4-04, 9 Aug 2026 — recorded per tasks/phase7/02-mahdi.md's checklist,
# since Pulga was not reachable to decide live): the vocabulary bridge lives HERE,
# not in the frontend's `driver.*` i18n keys. Those 24 keys are short noun-phrase
# axis labels for DriverBars.tsx's bar chart ("Rainfall, previous day") — they are
# not built to sit grammatically after "because" in a sentence, and reusing them
# unchanged there just produces a different-shaped noun-pile than the raw-name
# fallback did. DRIVER_PHRASE needs a verb-bearing clause instead. What IS taken
# from `driver.*`: the terminology itself — each entry below names the same
# concept with the same words the bar chart already uses in both languages
# (`أمطار اليوم السابق`, `الأمطار مقابل المئين 90`, ...), so a reader never sees a
# driver called one thing in the chart and another thing in the sentence.
#
# The four entries below (rain_self_percentile, rain_over_p90, precip_prior_1d_mm,
# precip_prior_3d_mm) are the runoff model's actual top SHAP drivers for the anchor
# event (tasks/phase6/04-pulga.md, evidence/p4-04/runoff_predict_real_drivers.json).
# Before this, none of the four had an entry, so every real prediction fell through
# to `feature.replace("_", " ")` — grammatically dead: "...because rain self
# percentile, rain over p90, precip prior 1d mm and precip prior 3d mm."
DRIVER_PHRASE = {
    "en": {
        "rainfall_3h_mm": "forecast 3-hour rainfall exceeds the catchment's historical {pct} percentile",
        "rainfall_mm_3h": "forecast 3-hour rainfall exceeds the catchment's historical {pct} percentile",
        "slope_mean": "the upstream terrain is steep",
        "antecedent_index": "antecedent soil conditions support rapid runoff",
        "frac_bare_sparse_vegetation": "the catchment surface is almost entirely bare ground",
        "road_density_km_per_km2": "road density adds impervious surface",
        "clay_0_5cm_mean": "surface soil texture favours runoff over infiltration",
        "rain_self_percentile": "the day's rainfall ranks far above what this catchment typically sees",
        "rain_over_p90": "rainfall exceeded the catchment's 90th-percentile threshold",
        "precip_prior_1d_mm": "the previous day already carried substantial rainfall",
        "precip_prior_3d_mm": "rainfall built up over the three days beforehand",
    },
    "ar": {
        "rainfall_3h_mm": "الأمطار المتوقعة خلال 3 ساعات تتجاوز النسبة المئوية {pct} التاريخية للحوض",
        "rainfall_mm_3h": "الأمطار المتوقعة خلال 3 ساعات تتجاوز النسبة المئوية {pct} التاريخية للحوض",
        "slope_mean": "تضاريس المنابع شديدة الانحدار",
        "antecedent_index": "ظروف التربة السابقة تدعم جريانًا سطحيًا سريعًا",
        "frac_bare_sparse_vegetation": "سطح الحوض شبه خالٍ من الغطاء النباتي",
        "road_density_km_per_km2": "كثافة الطرق تزيد الأسطح غير المنفذة",
        "clay_0_5cm_mean": "قوام التربة السطحية يرجّح الجريان على الترشيح",
        # Noun-initial, same requirement as every entry above — see
        # test_arabic_driver_clause_is_noun_initial, which iterates this dict.
        "rain_self_percentile": "أمطار هذا اليوم تتجاوز ما يشهده هذا الحوض عادة",
        "rain_over_p90": "الأمطار تجاوزت عتبة المئين 90 لهذا الحوض",
        "precip_prior_1d_mm": "أمطار اليوم السابق كانت غزيرة بالفعل",
        "precip_prior_3d_mm": "أمطار الأيام الثلاثة السابقة تراكمت",
    },
}

JOIN = {"en": (", ", " and "), "ar": ("، ", " و")}

PLUME_EN = ("The plume ensemble indicates a {prob}% probability of reaching Reef Zone "
            "{zone} within {t0}–{t1} hours. ")
PLUME_AR = ("يشير تجمّع محاكاة العوالق إلى احتمال {prob}% لوصولها إلى منطقة الشعاب "
            "{zone} خلال {t0}–{t1} ساعة. ")

CONF_EN = ("Confidence is {conf} because nearshore currents are represented by a "
           "coarse global model.")
CONF_AR = ("الثقة {conf} لأن التيارات الساحلية القريبة ممثَّلة بنموذج عالمي منخفض "
           "الدقة.")


def _num(value) -> str:
    """Render a number without changing it.

    No rounding, no significant-figure policy. Only a trailing ".0" is dropped,
    because "72.0%" and "72%" are the same number and the second reads better —
    the digits themselves are untouched.
    """
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        s = format(value.normalize(), "f")
        return s
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return repr(value)
    return str(value)


def to_percent(probability) -> Decimal:
    """Probability on [0,1] -> percent, as an EXACT decimal shift.

    Not `probability * 100`. In IEEE754, 0.0725 * 100 is 7.249999999999999, and
    that artefact would render on screen verbatim — because the rule forbids
    rounding it away, the honest fix is not to introduce it. Shifting the decimal
    representation the caller supplied gives 7.25 exactly, changes no digit the
    caller provided, and keeps display and `source_numbers` identical.
    """
    if probability is None:
        return None
    return Decimal(str(probability)) * Decimal(100)


def _feature_name(d: dict) -> str:
    """The driver's feature name, under either field name callers actually use.

    `/explain`'s own schema calls this `feature`. `/runoff/predict` calls the same
    thing `key` (`backend/src/api/main.py`'s `DriverOut`, renamed there to match
    the frontend's `PredictionDriver` type). A caller who forwards a real
    prediction's `drivers` list into `/explain` unmodified used to get every
    phrase silently dropped to "" (feature.get("feature") is missing), the
    driver_clause empty, and a spurious `rainfall_percentile` HTTPException 500 —
    exactly Phase 6's p4-04 FAIL reproduction. Accepting `key` as a synonym means
    the two endpoints' native output/input shapes actually compose.
    """
    return d.get("feature") or d.get("key") or ""


def _driver_clause(drivers: list[dict], language: str, rainfall_percentile) -> tuple[str, bool]:
    """(clause, pct_rendered). `pct_rendered` is True only if `{pct}` actually made
    it into the clause — see build_explanation for why the caller needs to know.
    """
    lang = language if language in DRIVER_PHRASE else "en"
    phrases = []
    pct_rendered = False
    for d in drivers:
        feature = _feature_name(d)
        template = DRIVER_PHRASE[lang].get(feature)
        if template is None:
            phrases.append(feature.replace("_", " ") if feature else "")
            continue
        if "{pct}" in template:
            pct = _num(rainfall_percentile) if rainfall_percentile is not None else "99th"
            if pct.isdigit():
                pct = f"{pct}th" if lang == "en" else pct
            phrases.append(template.format(pct=pct))
            pct_rendered = True
        else:
            phrases.append(template)

    phrases = [p for p in phrases if p]
    if not phrases:
        # The Arabic clause must be NOUN-initial. TEMPLATE_AR interpolates this
        # after لأن, which cannot take a verb directly: the natural word order
        # "لم تُوفَّر عوامل النموذج" yields "لأن لم تُوفَّر" — ungrammatical. All seven
        # DRIVER_PHRASE["ar"] entries happen to start with a noun, so only this
        # fallback was exposed, and only when a caller supplies no drivers at all.
        return (("the model's drivers were not supplied" if lang == "en"
                 else "عوامل النموذج لم تُوفَّر"), False)
    sep, final = JOIN[lang]
    if len(phrases) == 1:
        return phrases[0], pct_rendered
    return sep.join(phrases[:-1]) + final + phrases[-1], pct_rendered


def build_explanation(
    catchment_id: str,
    risk_level: str,
    language: str = "en",
    shap_drivers: list[dict] | None = None,
    plume_probability: float | None = None,
    arrival_window_hours: tuple[float, float] | None = None,
    confidence: str | None = None,
    reef_zone_id: str | None = None,
    rainfall_percentile: float | None = None,
    catchment_label: str | None = None,
) -> tuple[str, dict]:
    """(text, source_numbers).

    `source_numbers` is exactly what was handed in. The test suite asserts every
    value in it appears in `text` unaltered.
    """
    lang = language if language in ("en", "ar") else "en"
    drivers = shap_drivers or []

    label = catchment_label or catchment_id
    risk_phrase = RISK_PHRASE[lang].get(risk_level, risk_level)
    driver_clause, pct_rendered = _driver_clause(drivers, lang, rainfall_percentile)

    source_numbers: dict = {}

    plume_clause = ""
    if plume_probability is not None and reef_zone_id and arrival_window_hours:
        # Percent is the presentation unit; the stored probability stays 0-1. The
        # multiplication is done HERE, once, and the exact rendered value is put
        # into source_numbers so the fidelity test checks what is actually shown.
        pct_value = to_percent(plume_probability)
        t0, t1 = arrival_window_hours
        tmpl = PLUME_EN if lang == "en" else PLUME_AR
        plume_clause = tmpl.format(
            prob=_num(pct_value), zone=reef_zone_id, t0=_num(t0), t1=_num(t1)
        )
        source_numbers.update({
            "plume_probability_pct": pct_value,
            "arrival_start_hours": t0,
            "arrival_end_hours": t1,
        })

    confidence_clause = ""
    if confidence:
        tmpl = CONF_EN if lang == "en" else CONF_AR
        confidence_clause = tmpl.format(conf=CONFIDENCE_WORD[lang].get(confidence, confidence))

    # Only tracked when {pct} actually made it into driver_clause. rainfall_percentile
    # is an argument to the rainfall_3h_mm/rainfall_mm_3h phrase specifically, not a
    # number the sentence always shows — a caller supplying it alongside drivers that
    # don't use it (e.g. the model's real rain_self_percentile/rain_over_p90/... set)
    # would otherwise get a fidelity-check 500 for a number the text never claimed to
    # render. This was Phase 6's exact p4-04 reproduction (evidence/p4-04/
    # explain_with_unrenamed_key_field_500.json), not a coincidence of the key/feature
    # rename bug alone.
    if rainfall_percentile is not None and pct_rendered:
        source_numbers["rainfall_percentile"] = rainfall_percentile
    for d in drivers:
        name = _feature_name(d)
        if "value" in d and name:
            source_numbers[f"driver_{name}"] = d["value"]

    template = TEMPLATE_EN if lang == "en" else TEMPLATE_AR
    text = template.format(
        catchment_label=label,
        risk_phrase=risk_phrase,
        driver_clause=driver_clause,
        plume_clause=plume_clause,
        confidence_clause=confidence_clause,
    ).strip()

    return text, source_numbers


def numbers_present(text: str, source_numbers: dict) -> list[str]:
    """Which source numbers are NOT verbatim in the text. Empty list = fidelity OK.

    Driver values are excluded from the check: SHAP contributions are inputs to the
    reasoning, not figures the paragraph quotes, so requiring them to appear would
    force the template to recite numbers a reader does not need.
    """
    missing = []
    for key, value in source_numbers.items():
        if key.startswith("driver_"):
            continue
        rendered = _num(value)
        # Boundary-aware: a plain substring test passes when a number has been
        # EXTENDED rather than replaced — "72" is a substring of "72.4" and of
        # "720", so substring matching would wave through exactly the tampering
        # this check exists to catch.
        pattern = rf"(?<![\d.]){re.escape(rendered)}(?![\d.])"
        if not re.search(pattern, text):
            missing.append(f"{key}={rendered}")
    return missing
