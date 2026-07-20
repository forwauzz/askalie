"""Background job registry for the review app.

One job per case at a time (ingestion or chronology), run in a daemon thread
so the UI stays responsive. State is in-process — fine for a local app.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Job:
    case_id: str
    stage: str  # "ingestion" | "chronology"
    status: str = "running"  # running | done | failed
    error: str | None = None
    started_at: float = field(default_factory=time.time)


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, case_id: str) -> Job | None:
        return self._jobs.get(case_id)

    def is_running(self, case_id: str) -> bool:
        job = self.get(case_id)
        return job is not None and job.status == "running"

    def start(self, case_id: str, stage: str, target: Callable[[], None]) -> bool:
        with self._lock:
            if self.is_running(case_id):
                return False
            job = Job(case_id=case_id, stage=stage)
            self._jobs[case_id] = job

        def runner() -> None:
            try:
                target()
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 - job errors surface in the UI
                job.status = "failed"
                job.error = f"{exc}"
                traceback.print_exc()

        threading.Thread(target=runner, daemon=True, name=f"{stage}-{case_id}").start()
        return True
