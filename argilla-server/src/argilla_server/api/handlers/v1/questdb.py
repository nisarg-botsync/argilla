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

from fastapi import APIRouter, Query, Security
from fastapi.responses import JSONResponse

from argilla_server.contexts import questdb
from argilla_server.models import User
from argilla_server.security import auth

router = APIRouter(tags=["questdb"])


@router.get("/questdb/exec")
async def exec_questdb_query(
    *,
    query: str = Query(..., description="SQL to run on QuestDB. Only read-only statements are accepted"),
    limit: int = Query(200, ge=1, description="Max number of rows to return"),
    current_user: User = Security(auth.get_current_user),
):
    # The body keeps QuestDB's /exec shape ("error", "columns", "dataset", "timings")
    # so that the SQL review panel reads errors and results the same way
    try:
        status_code, body = await questdb.execute_query(query, limit)
    except questdb.QuestDBNotConfiguredError:
        status_code, body = 503, {"query": query, "error": "QuestDB is not configured. Set ARGILLA_QUESTDB_URL."}

    return JSONResponse(status_code=status_code, content=body)
