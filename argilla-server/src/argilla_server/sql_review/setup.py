#  Copyright 2021-present, the Recognai S.L. team.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Puts the SQL review panel into datasets that have a text field named "sql".

For each dataset:
- old format (SQL as a text field) with no annotations: copy it into a new dataset
  where the SQL field is the panel, and rename the old one to "<name> - archived".
- old format with annotations: skip it, so that no annotation is lost.
- new format (SQL field is the panel): refresh the panel, so that changed settings apply.
- listed in a backup file but missing on the server: create it from the backup.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

SQL_FIELD = "sql"
PANEL_PATH = Path(__file__).parent / "panel.html"
PAGE_SIZE = 500
BULK_SIZE = 100


def render_panel(slow_query_seconds: float) -> str:
    panel = PANEL_PATH.read_text()
    return re.sub(r"const SLOW_QUERY_SECONDS = [0-9.]+;", f"const SLOW_QUERY_SECONDS = {slow_query_seconds:g};", panel)


def strip_fence(sql: str) -> str:
    match = re.match(r"\s*```[a-zA-Z]*\n(.*?)\n?```\s*$", sql, re.S)
    return (match.group(1) if match else sql).strip()


def _keep(item: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: item[key] for key in keys if key in item}


def _panel_settings(panel: str) -> Dict[str, Any]:
    return {"type": "custom", "template": panel, "advanced_mode": True}


class SqlReviewSetup:
    def __init__(self, api_url: str, log: Callable[[str], None] = print):
        self._client = httpx.Client(base_url=api_url.rstrip("/") + "/api", timeout=60)
        self._log = log

    def login(self, username: str, password: str, wait_seconds: int = 300) -> None:
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                response = self._client.post("/v1/token", data={"username": username, "password": password})
                response.raise_for_status()
                break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(2)
        self._client.headers["Authorization"] = "Bearer " + response.json()["access_token"]

    def use_api_key(self, api_key: str) -> None:
        self._client.headers["X-Argilla-Api-Key"] = api_key

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self._client.request(method, path, json=body)
        if response.is_error:
            raise RuntimeError(f"{method} {path} -> {response.status_code} {response.text[:500]}")
        return response.json()

    def export(self, dataset_id: str) -> Dict[str, Any]:
        """Reads a dataset in the shape of a backup file entry."""
        records, offset = [], 0
        while True:
            page = self._call(
                "GET", f"/v1/datasets/{dataset_id}/records?limit={PAGE_SIZE}&offset={offset}&include=responses"
            )["items"]
            records += page
            offset += len(page)
            if len(page) < PAGE_SIZE:
                break
        return {
            "dataset": self._call("GET", f"/v1/datasets/{dataset_id}"),
            "fields": self._call("GET", f"/v1/datasets/{dataset_id}/fields")["items"],
            "questions": self._call("GET", f"/v1/datasets/{dataset_id}/questions")["items"],
            "metadata_properties": self._call("GET", f"/v1/me/datasets/{dataset_id}/metadata-properties")["items"],
            "records": records,
        }

    def create(self, source: Dict[str, Any], name: str, workspace_id: str, panel: str) -> str:
        dataset = source["dataset"]
        dataset_id = self._call(
            "POST",
            "/v1/datasets",
            {
                "name": name,
                "guidelines": dataset.get("guidelines"),
                "allow_extra_metadata": dataset.get("allow_extra_metadata", False),
                "distribution": dataset.get("distribution"),
                "workspace_id": workspace_id,
            },
        )["id"]

        for field in source["fields"]:
            if field["name"] == SQL_FIELD:
                field = {**_keep(field, ["name", "title", "required"]), "settings": _panel_settings(panel)}
            self._call(
                "POST", f"/v1/datasets/{dataset_id}/fields", _keep(field, ["name", "title", "required", "settings"])
            )
        for question in source["questions"]:
            self._call(
                "POST",
                f"/v1/datasets/{dataset_id}/questions",
                _keep(question, ["name", "title", "description", "required", "settings"]),
            )
        for prop in source["metadata_properties"]:
            self._call(
                "POST",
                f"/v1/datasets/{dataset_id}/metadata-properties",
                _keep(prop, ["name", "title", "settings", "visible_for_annotators"]),
            )
        self._call("PUT", f"/v1/datasets/{dataset_id}/publish")

        items = []
        for record in source["records"]:
            fields = dict(record["fields"])
            sql = fields.get(SQL_FIELD)
            if isinstance(sql, str):
                fields[SQL_FIELD] = {"sql": strip_fence(sql)}
            items.append({"fields": fields, "metadata": record.get("metadata"), "external_id": record.get("external_id")})
        for start in range(0, len(items), BULK_SIZE):
            self._call("POST", f"/v1/datasets/{dataset_id}/records/bulk", {"items": items[start : start + BULK_SIZE]})

        self._log(f"created '{name}' with {len(items)} records")
        return dataset_id

    def upgrade(self, dataset_id: str, name: str, panel: str) -> None:
        source = self.export(dataset_id)
        answered = sum(1 for record in source["records"] if record.get("responses"))
        if answered:
            self._log(f"skipped '{name}': {answered} records have annotations, migrate it by hand")
            return

        new_id = self.create(source, name + " (new)", source["dataset"]["workspace_id"], panel)
        self._call("PATCH", f"/v1/datasets/{dataset_id}", {"name": name + " - archived"})
        self._call("PATCH", f"/v1/datasets/{new_id}", {"name": name})
        self._log(f"upgraded '{name}', the old dataset is now '{name} - archived'")

    def refresh(self, sql_field: Dict[str, Any], name: str, panel: str) -> None:
        self._call("PATCH", f"/v1/fields/{sql_field['id']}", {"settings": _panel_settings(panel)})
        self._log(f"refreshed the panel of '{name}'")

    def run(self, slow_query_seconds: float, backup: Optional[Path] = None, workspace: Optional[str] = None) -> None:
        panel = render_panel(slow_query_seconds)
        existing = {dataset["name"]: dataset for dataset in self._call("GET", "/v1/me/datasets")["items"]}

        for name, dataset in existing.items():
            if name.endswith(" - archived"):
                continue
            sql_field = next(
                (f for f in self._call("GET", f"/v1/datasets/{dataset['id']}/fields")["items"] if f["name"] == SQL_FIELD),
                None,
            )
            if sql_field is None:
                continue
            if sql_field["settings"]["type"] == "custom":
                self.refresh(sql_field, name, panel)
            elif sql_field["settings"]["type"] == "text":
                self.upgrade(dataset["id"], name, panel)

        if backup:
            workspace_id = self._workspace_id(workspace)
            for name, source in json.loads(backup.read_text()).items():
                if name not in existing:
                    self.create(source, name, workspace_id, panel)

        self._log(f"done, slow query limit {slow_query_seconds:g} s")

    def _workspace_id(self, name: Optional[str]) -> str:
        workspaces = self._call("GET", "/v1/me/workspaces")["items"]
        match = next((w for w in workspaces if w["name"] == name), None) or (workspaces[0] if workspaces else None)
        if match is None:
            match = self._call("POST", "/v1/workspaces", {"name": name or "default"})
        return match["id"]
