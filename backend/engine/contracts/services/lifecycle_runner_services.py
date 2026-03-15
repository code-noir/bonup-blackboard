# backend/engine/contracts/services/lifecycle_runner_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Any
from backend.engine.contracts.obligations.lifecycle import (
    process_obligation_lifecycle,
)



@dataclass
class LifecycleTickResult:
    scanned: int
    updated: int
    unchanged: int
    changed_ids: List[str]


class LifecycleRunnerService:
    def __init__(self, obligation_repo):
        self.obligation_repo = obligation_repo

    def run(self, current_time=None):
        """
        Runs lifecycle processing for all obligations.
        """

        obligations = self.obligation_repo.get_all()

        for obligation in obligations:
            process_obligation_lifecycle(
                obligation,
                obligation_repo=self.obligation_repo,
                current_time=current_time,
            )


    

    def tick(
        self,
        *,
        current_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        contract_id: Optional[str] = None,
    ) -> LifecycleTickResult:
        """
        Evaluate lifecycle for obligations and persist state changes.

        Args:
            current_time: REQUIRED for correct lifecycle logic consistency.
                         If not provided, we use utcnow().
            limit: optional cap (useful for debugging / batching)
            contract_id: optional filter to run lifecycle for one contract

        Returns:
            LifecycleTickResult summary.
        """
        if current_time is None:
            current_time = datetime.utcnow()

        candidates = list(
            self.obligation_repo.list_candidates(
                contract_id=contract_id,
                limit=limit,
            )
        )

        scanned = 0
        updated = 0
        unchanged = 0
        changed_ids: List[str] = []

        for ob in candidates:
            scanned += 1

            # We evaluate and mutate state via engine logic.
            # process_obligation_lifecycle returns the NEW state string.
            new_state = process_obligation_lifecycle(ob, current_time)

            old_state = getattr(ob, "state", None)

            # Only persist if changed
            if old_state != new_state:
                self.obligation_repo.update_state(
                    obligation=ob,
                    new_state=new_state,
                    current_time=current_time,
                )
                updated += 1
                changed_ids.append(str(getattr(ob, "id", "")))
            else:
                unchanged += 1

        return LifecycleTickResult(
            scanned=scanned,
            updated=updated,
            unchanged=unchanged,
            changed_ids=changed_ids,
        )


