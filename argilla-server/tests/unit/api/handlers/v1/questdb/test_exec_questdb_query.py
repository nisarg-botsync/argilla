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

from unittest import mock

import httpx
import pytest
import respx
from httpx import AsyncClient, Response

from argilla_server.constants import API_KEY_HEADER_NAME
from argilla_server.settings import settings

from tests.factories import AnnotatorFactory

QUESTDB_URL = "http://questdb.test:9000"
QUESTDB_RESULT = {
    "query": "select 1",
    "columns": [{"name": "1", "type": "INT"}],
    "timestamp": -1,
    "dataset": [[1]],
    "count": 1,
    "timings": {"authentication": 1, "compiler": 2, "execute": 3, "count": 0},
}


@pytest.fixture
def questdb_url():
    with mock.patch.object(settings, "questdb_url", QUESTDB_URL):
        yield QUESTDB_URL


@pytest.mark.asyncio
class TestExecQuestDBQuery:
    def url(self) -> str:
        return "/api/v1/questdb/exec"

    async def test_exec_questdb_query(self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock):
        route = respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(200, json=QUESTDB_RESULT))

        response = await async_client.get(self.url(), params={"query": "select 1"}, headers=owner_auth_header)

        assert response.status_code == 200
        assert response.json() == QUESTDB_RESULT
        params = route.calls.last.request.url.params
        assert params["query"] == "select 1"
        assert params["limit"] == "200"
        assert params["timings"] == "true"

    async def test_exec_questdb_query_as_annotator(self, async_client: AsyncClient, questdb_url, respx_mock):
        annotator = await AnnotatorFactory.create()
        respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(200, json=QUESTDB_RESULT))

        response = await async_client.get(
            self.url(), params={"query": "select 1"}, headers={API_KEY_HEADER_NAME: annotator.api_key}
        )

        assert response.status_code == 200

    async def test_exec_questdb_query_without_authentication(self, async_client: AsyncClient, questdb_url):
        response = await async_client.get(self.url(), params={"query": "select 1"})

        assert response.status_code == 401

    async def test_exec_questdb_query_with_leading_comments(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(200, json=QUESTDB_RESULT))
        query = "-- Step 1: count each node's hits\n/* block */\nWITH hits AS (SELECT 1) SELECT * FROM hits;"

        response = await async_client.get(self.url(), params={"query": query}, headers=owner_auth_header)

        assert response.status_code == 200

    async def test_exec_questdb_query_caps_limit(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        route = respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(200, json=QUESTDB_RESULT))

        with mock.patch.object(settings, "questdb_max_rows", 50):
            await async_client.get(self.url(), params={"query": "select 1", "limit": 5000}, headers=owner_auth_header)

        assert route.calls.last.request.url.params["limit"] == "50"

    @pytest.mark.parametrize(
        "query",
        [
            "drop table trades",
            "INSERT INTO trades VALUES (1)",
            "-- select\nTRUNCATE TABLE trades",
            "select 1; drop table trades",
            "   ",
        ],
    )
    async def test_exec_questdb_query_rejects_write_queries(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock, query: str
    ):
        route = respx_mock.get(f"{questdb_url}/exec")

        response = await async_client.get(self.url(), params={"query": query}, headers=owner_auth_header)

        assert response.status_code == 400
        assert response.json()["error"]
        assert not route.called

    async def test_exec_questdb_query_allows_semicolon_inside_string(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(200, json=QUESTDB_RESULT))

        response = await async_client.get(
            self.url(), params={"query": "select 'a;b' from t"}, headers=owner_auth_header
        )

        assert response.status_code == 200

    async def test_exec_questdb_query_passes_questdb_errors(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        error = {"query": "select x from missing", "error": "table does not exist [table=missing]", "position": 14}
        respx_mock.get(f"{questdb_url}/exec").mock(return_value=Response(400, json=error))

        response = await async_client.get(
            self.url(), params={"query": "select x from missing"}, headers=owner_auth_header
        )

        assert response.status_code == 400
        assert response.json() == error

    async def test_exec_questdb_query_when_questdb_is_unreachable(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        respx_mock.get(f"{questdb_url}/exec").mock(side_effect=httpx.ConnectError("connection refused"))

        response = await async_client.get(self.url(), params={"query": "select 1"}, headers=owner_auth_header)

        assert response.status_code == 502
        assert "Could not reach QuestDB" in response.json()["error"]

    async def test_exec_questdb_query_when_questdb_times_out(
        self, async_client: AsyncClient, owner_auth_header: dict, questdb_url, respx_mock
    ):
        respx_mock.get(f"{questdb_url}/exec").mock(side_effect=httpx.ReadTimeout("timed out"))

        response = await async_client.get(self.url(), params={"query": "select 1"}, headers=owner_auth_header)

        assert response.status_code == 504

    async def test_exec_questdb_query_without_questdb_url(self, async_client: AsyncClient, owner_auth_header: dict):
        with mock.patch.object(settings, "questdb_url", None):
            response = await async_client.get(self.url(), params={"query": "select 1"}, headers=owner_auth_header)

        assert response.status_code == 503
        assert "ARGILLA_QUESTDB_URL" in response.json()["error"]
