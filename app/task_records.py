"""Shared helpers for task data capture: resolving target records and entity labels.

Used by activities router and future AI workflows.
"""
from __future__ import annotations

import json
from typing import Any


def _entity_name(table_name: str) -> str:
    """Map registry table name (e.g. 'core.meeting') to engine entity key ('meeting')."""
    return table_name.split(".")[-1]


def _label(column_name: str) -> str:
    """Turn a database column name into a human label (e.g. 'meeting_date' -> 'Meeting date')."""
    parts = column_name.replace("_", " ").strip()
    return parts[:1].upper() + parts[1:] if parts else ""


def _target_record(conn: Any, request: Any, task: dict, binding: dict) -> dict | None:
    """Find the record that binding points to, scoped to task or activity instance."""
    table_name = binding["table_name"]
    entity = _entity_name(table_name)
    instance_id = task["instance_id"]
    task_id = task["id"]

    # 1. Look for a task_record_link for this task
    rows = conn.execute(
        """SELECT entity_id FROM ops.task_record_link
           WHERE task_instance_id = %s AND entity_type = %s AND NOT is_archived
           ORDER BY id""",
        (task_id, entity),
    ).fetchall()

    # If not on this task, check any task in the same instance
    if not rows:
        rows = conn.execute(
            """SELECT l.entity_id FROM ops.task_record_link l
               JOIN ops.task_instance t ON t.id = l.task_instance_id
               WHERE t.instance_id = %s AND l.entity_type = %s AND NOT l.is_archived
               ORDER BY l.id""",
            (instance_id, entity),
        ).fetchall()

    target_id = None
    if rows:
        if len(rows) == 1 or not binding.get("row_filter"):
            target_id = rows[0]["entity_id"]
        else:
            rf = binding.get("row_filter")
            if isinstance(rf, str):
                try:
                    rf = json.loads(rf)
                except Exception:
                    rf = {}
            if isinstance(rf, dict) and rf:
                for r in rows:
                    candidate = conn.execute(
                        f"SELECT * FROM {table_name} WHERE id = %s AND NOT is_archived",
                        (r["entity_id"],),
                    ).fetchone()
                    if candidate and all(candidate.get(k) == v for k, v in rf.items()):
                        target_id = r["entity_id"]
                        break
            if target_id is None:
                target_id = rows[0]["entity_id"]

    # Fallback: if no link exists yet for 'meeting', check if a core.meeting exists for the company and meeting_date
    if target_id is None and entity == "meeting":
        inst = conn.execute(
            "SELECT company_id, params FROM ops.activity_instance WHERE id = %s",
            (instance_id,),
        ).fetchone()
        if inst and inst.get("params") and inst["params"].get("meeting_date"):
            m = conn.execute(
                "SELECT id FROM core.meeting WHERE company_id = %s AND meeting_date = %s AND NOT is_archived ORDER BY id DESC LIMIT 1",
                (inst["company_id"], inst["params"]["meeting_date"]),
            ).fetchone()
            if m:
                target_id = m["id"]

    if target_id is None:
        return None

    return conn.execute(
        f"SELECT * FROM {table_name} WHERE id = %s AND NOT is_archived",
        (target_id,),
    ).fetchone()
