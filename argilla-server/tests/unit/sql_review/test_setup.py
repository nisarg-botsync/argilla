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

import pytest

from argilla_server.sql_review.setup import render_panel, strip_fence


class TestRenderPanel:
    def test_sets_slow_query_seconds(self):
        panel = render_panel(4.5)

        assert "const SLOW_QUERY_SECONDS = 4.5;" in panel

    def test_calls_the_argilla_questdb_endpoint(self):
        panel = render_panel(3)

        assert '"/api/v1/questdb/exec"' in panel
        assert "auth._token.local" in panel


class TestStripFence:
    @pytest.mark.parametrize(
        "sql, expected",
        [
            ("```sql\nselect 1\n```", "select 1"),
            ("```\nselect 1;\n```\n", "select 1;"),
            ("  select 1  ", "select 1"),
        ],
    )
    def test_strip_fence(self, sql: str, expected: str):
        assert strip_fence(sql) == expected
