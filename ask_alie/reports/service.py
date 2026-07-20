"""Report unit creation and safe-text assembly (PLAN P4.1)."""

from __future__ import annotations

from ask_alie.reports.map import load_report_map, save_report_map
from ask_alie.reports.models import ReportUnit
from ask_alie.workspace.paths import CasePaths

PAGE_MARKER = "=== {document_id} page {page} ==="


def create_units_from_specs(paths: CasePaths, specs: list[dict]) -> list[ReportUnit]:
    """Create report units from manual specs and assemble their safe text.

    Each spec: {document_id, page_start, page_end, document_type?, title?}.
    Numbering continues from any existing report map.
    """
    units = load_report_map(paths)
    next_number = len(units) + 1
    for offset, spec in enumerate(specs):
        report_id = f"report_{next_number + offset:04d}"
        start, end = int(spec["page_start"]), int(spec["page_end"])
        unit = ReportUnit(
            report_id=report_id,
            document_id=spec["document_id"],
            page_start=start,
            page_end=end,
            page_ids=[f"{spec['document_id']}:p_{n:04d}" for n in range(start, end + 1)],
            document_type=spec.get("document_type", "unknown"),
            title=spec.get("title", ""),
            boundary_confidence=spec.get("boundary_confidence", "high"),
            boundary_reason=spec.get("boundary_reason", "manual import"),
        )
        assemble_report_text(paths, unit)
        units.append(unit)
    save_report_map(paths, units)
    return units


def assemble_report_text(paths: CasePaths, unit: ReportUnit) -> str:
    """Concatenate the unit's page safe texts with page markers; write to units/."""
    pieces: list[str] = []
    for page_number in range(unit.page_start, unit.page_end + 1):
        safe_path = paths.page_dir(unit.document_id) / f"page_{page_number:04d}.safe.txt"
        text = safe_path.read_text(encoding="utf-8") if safe_path.exists() else ""
        pieces.append(PAGE_MARKER.format(document_id=unit.document_id, page=page_number))
        pieces.append(text.rstrip())
    report_text = "\n".join(pieces) + "\n"
    out_path = paths.report_units_dir / f"{unit.report_id}.safe.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_text, encoding="utf-8")
    return report_text


def load_report_text(paths: CasePaths, report_id: str) -> str:
    return (paths.report_units_dir / f"{report_id}.safe.txt").read_text(encoding="utf-8")
