"""B5 — Post-Event Forensic Report Generator.

Assembles a draft report by retrieving real `formula_terms`, real stored
exposure results, real mooring measurements, and real RAG-corpus citations —
**never computes a new number itself** (Standing Law rule 12, same as B4).
Every `Claim.source` is either a real citation/formula_terms key or explicitly
`None` with plain text saying the data doesn't exist — this module's
"missing is never zero" obligation, applied to narrative text instead of a
number.

Deterministic templating, same convention as `rag/explain.py` and B4's
`site_scoring.py`: no generative model call anywhere in this path
(`rag/answer.py::generate_with_llm` is a permanent stub in this codebase).

A pure computation module, same division of labour as `runoff_model.py` and
`site_scoring.py`: takes already-fetched data as plain arguments rather than
importing `api.data_access`/`exposure.store`/`rag.index` itself — `main.py`
does the fetching, this module only assembles.
"""

from __future__ import annotations


def assemble_report(
    event_id: str,
    exposure_run: dict | None,
    mooring: dict | None,
    rag_chunks: list[dict],
) -> list[dict]:
    """Return `list[{"title": str, "claims": [{"text": str, "source": str|None}]}]`.

    `exposure_run` — a dict from `exposure.store.get_run()`/`latest_run()`, or
    `None` if no run has ever been stored for this event (a real gap, reported
    as one, not silently skipped).
    `mooring` — a dict from `data_access.mooring_for()`, or `None`.
    `rag_chunks` — the raw list of dicts from `rag.index.retrieve()`.
    """
    sections: list[dict] = []

    if exposure_run is None:
        sections.append({
            "title": "Exposure summary",
            "claims": [{
                "text": f"No exposure run has been stored for {event_id}. This "
                        "section is empty because the data doesn't exist yet, "
                        "not because it was omitted.",
                "source": None,
            }],
        })
    else:
        claims = []
        for r in exposure_run["results"]:
            claims.append({
                "text": (
                    f"Zone {r['reef_zone_id']} reached {r['risk_level']} "
                    f"({r['risk_score']:.1f}/100), confidence {r['confidence']}."
                ),
                "source": f"exposure_run:{exposure_run['run_id']}#{r['reef_zone_id']}",
            })
            # The formula_terms that produced the number above, cited by key —
            # not re-stated as prose, since a sentence can't be checked for
            # fidelity as cheaply as a dict lookup can.
            for term_key in ("plume_probability", "relative_sediment_intensity",
                             "transmission_loss", "confidence_adjustment_reason"):
                if r["formula_terms"].get(term_key) is not None:
                    claims.append({
                        "text": f"{r['reef_zone_id']}.{term_key} = "
                                f"{r['formula_terms'][term_key]!r}",
                        "source": f"exposure_run:{exposure_run['run_id']}"
                                  f"#{r['reef_zone_id']}.formula_terms",
                    })
        sections.append({"title": "Exposure summary", "claims": claims})

        if exposure_run.get("caveats"):
            sections.append({
                "title": "Caveats carried with this run",
                "claims": [
                    {"text": c["message"], "source": c.get("source")}
                    for c in exposure_run["caveats"]
                ],
            })

    if mooring is None:
        sections.append({
            "title": "Sensor validation",
            "claims": [{
                "text": f"No mooring record exists for {event_id}. The demo "
                        "anchor event (AQ-2016-10-28) has one real, cited "
                        "mooring target; most other events do not.",
                "source": None,
            }],
        })
    else:
        magnitude_claims = []
        for key in ("peak_suspended_sediment_g_l", "salinity_minimum_psu",
                    "salinity_anomaly_delta_psu", "sediment_mass_total_t"):
            value = mooring.get("magnitude", {}).get(key)
            if value is not None:
                magnitude_claims.append({
                    "text": f"Measured {key.replace('_', ' ')}: {value}",
                    "source": mooring.get("source_citation"),
                })
        sections.append({"title": "Sensor validation", "claims": magnitude_claims or [
            {"text": "Mooring record exists but carries no magnitude fields.",
             "source": mooring.get("source_citation")},
        ]})

    if rag_chunks:
        sections.append({
            "title": "Related documentation",
            "claims": [
                {"text": c["excerpt"], "source": f"{c['source_file']}#{c['section']}"}
                for c in rag_chunks
            ],
        })
    else:
        sections.append({
            "title": "Related documentation",
            "claims": [{
                "text": "No corpus passages retrieved for this event — the "
                        "documentation this project has may simply not "
                        "discuss it, which is itself worth knowing.",
                "source": None,
            }],
        })

    return sections
