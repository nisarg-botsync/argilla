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

import re
from typing import Any, Dict, Tuple

import httpx

from argilla_server.settings import settings

READ_ONLY_KEYWORDS = {"select", "with", "explain", "show", "declare"}

# Comments and string literals, matched in one pass so that quotes in comments and
# comment markers in strings do not confuse each other
_COMMENTS_AND_STRINGS = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'", re.DOTALL)


class QuestDBNotConfiguredError(Exception):
    pass


def read_only_error(query: str) -> str:
    """Returns why the query is not a single read-only statement, or an empty string if it is."""
    code = _COMMENTS_AND_STRINGS.sub(lambda m: "''" if m.group(0).startswith("'") else " ", query).strip()
    if not code:
        return "The query is empty."

    first_word = code.split(None, 1)[0].lower()
    if first_word not in READ_ONLY_KEYWORDS:
        return f"Only read-only queries can run here ({', '.join(sorted(READ_ONLY_KEYWORDS)).upper()})."

    if code.rstrip(";").strip().count(";"):
        return "Only one statement can run at a time."

    return ""


async def execute_query(query: str, limit: int) -> Tuple[int, Dict[str, Any]]:
    """Runs a read-only query on QuestDB. Returns QuestDB's HTTP status and JSON body."""
    if not settings.questdb_url:
        raise QuestDBNotConfiguredError()

    error = read_only_error(query)
    if error:
        return 400, {"query": query, "error": error}

    params = {"query": query, "limit": min(limit, settings.questdb_max_rows), "timings": "true"}
    try:
        async with httpx.AsyncClient(timeout=settings.questdb_timeout) as client:
            response = await client.get(settings.questdb_url.rstrip("/") + "/exec", params=params)
    except httpx.TimeoutException:
        return 504, {"query": query, "error": f"QuestDB did not answer in {settings.questdb_timeout:g} s."}
    except httpx.HTTPError as e:
        return 502, {"query": query, "error": f"Could not reach QuestDB: {e}"}

    try:
        return response.status_code, response.json()
    except ValueError:
        return 502, {"query": query, "error": f"QuestDB sent a response that is not JSON (HTTP {response.status_code})."}
