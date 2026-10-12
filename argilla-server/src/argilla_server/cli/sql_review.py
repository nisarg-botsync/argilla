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

from pathlib import Path
from typing import Optional

import typer

from argilla_server.sql_review.setup import SqlReviewSetup

app = typer.Typer(help="Commands for the SQL review panel", no_args_is_help=True)


@app.command(name="setup", help="Put the SQL review panel into every dataset that has a field named 'sql'.")
def setup(
    api_url: str = typer.Option("http://localhost:6900", envvar="ARGILLA_URL", help="Argilla server URL."),
    username: Optional[str] = typer.Option(None, envvar="USERNAME", help="Owner username."),
    password: Optional[str] = typer.Option(None, envvar="PASSWORD", help="Owner password."),
    api_key: Optional[str] = typer.Option(None, envvar="API_KEY", help="Owner API key, used without a username."),
    slow_query_seconds: float = typer.Option(
        3, envvar="SLOW_QUERY_SECONDS", help="Run time that flags a query as a performance issue."
    ),
    backup: Optional[Path] = typer.Option(
        None, envvar="SQL_REVIEW_BACKUP", exists=True, dir_okay=False, help="JSON file of datasets to create if missing."
    ),
    workspace: Optional[str] = typer.Option(None, envvar="WORKSPACE", help="Workspace for datasets from the backup."),
):
    runner = SqlReviewSetup(api_url, log=lambda message: typer.echo(f"[sql-review] {message}"))
    if username and password:
        runner.login(username, password)
    elif api_key:
        runner.use_api_key(api_key)
    else:
        raise typer.BadParameter("Set USERNAME and PASSWORD, or API_KEY.")

    runner.run(slow_query_seconds, backup=backup, workspace=workspace)


if __name__ == "__main__":
    app()
