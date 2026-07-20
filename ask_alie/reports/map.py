"""Report map persistence (Spec §10: reports/report_map.json)."""

from __future__ import annotations

import json

from ask_alie.reports.models import ReportUnit
from ask_alie.workspace.paths import CasePaths


def save_report_map(paths: CasePaths, units: list[ReportUnit]) -> None:
    paths.report_map.parent.mkdir(parents=True, exist_ok=True)
    payload = [unit.model_dump() for unit in units]
    paths.report_map.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_report_map(paths: CasePaths) -> list[ReportUnit]:
    if not paths.report_map.exists():
        return []
    return [
        ReportUnit.model_validate(raw)
        for raw in json.loads(paths.report_map.read_text(encoding="utf-8"))
    ]


def readable_units(paths: CasePaths) -> list[ReportUnit]:
    """Units worth dispatching readers to: skips superseded units, empty pages
    and units inside byte-identical duplicate documents (cost control)."""
    from ask_alie.workspace.manifest import load_manifest

    duplicate_docs: set[str] = set()
    if paths.manifest.exists():
        duplicate_docs = {
            d.document_id for d in load_manifest(paths).documents if d.duplicate_of
        }
    return [
        unit
        for unit in load_report_map(paths)
        if unit.status != "superseded"
        and unit.document_type != "empty"
        and unit.document_id not in duplicate_docs
    ]
