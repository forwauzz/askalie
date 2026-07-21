"""ALIE Legal Baseline v1 (Spec §26).

Kept as a Python constant instead of YAML to avoid a dependency; this is a
test configuration, not a client profile.
"""

BASELINE_NAME = "alie-legal-baseline-v1"

MANDATORY_DEFAULT: frozenset[str] = frozenset(
    {
        # legacy English taxonomy
        "accident",
        "emergency_visit",
        "imaging",
        "surgery",
        "expertise",
        "work_stoppage",
        "return_to_work_change",
        "functional_limitation",
        "consolidation",
        "permanent_impairment",
        "relapse_recurrence",
        "administrative_decision",
        # Cabinet-informed French taxonomy (master reader prompt)
        "accident du travail",
        "réclamation",
        "imagerie",
        "hospitalisation",
        "chirurgie",
        "arrêt de travail",
        "retour au travail",
        "assignation temporaire",
        "atteinte permanente",
        "limitations fonctionnelles",
        "avis bem",
        "décision cnesst",
        "décision dra",
        "décision tat",
    }
)

LIKELY_SECONDARY: frozenset[str] = frozenset(
    {
        "routine_prescription_renewal",
        "unchanged_followup",
        "duplicate_fax",
        "correspondance",
        "transmission",
    }
)
