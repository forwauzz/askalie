"""ALIE Legal Baseline v1 (Spec §26).

Kept as a Python constant instead of YAML to avoid a dependency; this is a
test configuration, not a client profile.
"""

BASELINE_NAME = "alie-legal-baseline-v1"

MANDATORY_DEFAULT: frozenset[str] = frozenset(
    {
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
    }
)

LIKELY_SECONDARY: frozenset[str] = frozenset(
    {
        "routine_prescription_renewal",
        "unchanged_followup",
        "duplicate_fax",
    }
)
