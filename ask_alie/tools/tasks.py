"""create_tasks and resolve_tasks tools (Spec §21.2)."""

from __future__ import annotations

from typing import Any

from ask_alie.tools.registry import ToolContext, tool
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.runlog import log_action
from ask_alie.workspace.tasks import AgentTask


def _store(ctx: ToolContext) -> JsonlStore[AgentTask]:
    return JsonlStore(ctx.paths.tasks_file, AgentTask)


@tool(
    "create_tasks",
    "Record follow-up tasks (from the Gap Agent or the orchestrator).",
    {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "target_ids": {"type": "array", "items": {"type": "string"}},
                        "priority": {"type": "string"},
                        "reason": {"type": "string"},
                        "instructions": {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
            "requested_by": {"type": "string"},
        },
        "required": ["tasks"],
    },
)
async def create_tasks(
    ctx: ToolContext, tasks: list[dict], requested_by: str = "orchestrator"
) -> dict[str, Any]:
    store = _store(ctx)
    existing = store.read_all()
    next_number = len(existing) + 1
    created: list[str] = []
    for offset, spec in enumerate(tasks):
        task = AgentTask(
            task_id=f"task_{next_number + offset:04d}",
            action=spec["action"],
            target_ids=spec.get("target_ids", []),
            requested_by=requested_by,
            reason=spec.get("reason", ""),
            priority=spec.get("priority", "medium"),
            instructions=spec.get("instructions"),
        )
        store.append(task)
        created.append(task.task_id)
    log_action(ctx.paths, actor=requested_by, action="create_tasks",
               targets=created, result={"count": len(created)})
    return {"created": created}


@tool(
    "resolve_tasks",
    "Mark tasks done (or failed) with a result summary.",
    {
        "type": "object",
        "properties": {
            "task_ids": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["done", "failed", "skipped"]},
            "result_summary": {"type": "string"},
        },
        "required": ["task_ids"],
    },
)
async def resolve_tasks(
    ctx: ToolContext,
    task_ids: list[str],
    status: str = "done",
    result_summary: str | None = None,
) -> dict[str, Any]:
    store = _store(ctx)
    tasks = store.read_all()
    known = {t.task_id for t in tasks}
    missing = [tid for tid in task_ids if tid not in known]
    if missing:
        return {"error": f"unknown tasks: {missing}"}
    for task in tasks:
        if task.task_id in task_ids:
            task.status = status
            task.result_summary = result_summary
            task.attempts += 1
    store.rewrite(tasks)
    return {"resolved": task_ids, "status": status}
