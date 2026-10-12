# SQL review panel

This build of Argilla server 2.8.0 helps annotators review SQL queries for QuestDB. A dataset field named `sql` shows the query with a "Try it out" button. The button opens an editor that runs the query and shows the result rows.

## What this branch adds

- `GET /api/v1/questdb/exec` runs a query on QuestDB and returns the QuestDB `/exec` response. Any signed-in user can call it. It accepts only one read-only statement (`SELECT`, `WITH`, `EXPLAIN`, `SHOW` or `DECLARE`). It returns at most `ARGILLA_QUESTDB_MAX_ROWS` rows.
- `python -m argilla_server sql-review setup` puts the panel into every dataset that has a field named `sql`. See "Setup command" below.
- The panel (`src/argilla_server/sql_review/panel.html`) is a custom field template. It calls the endpoint with the signed-in user's token. A run of the unedited query can take longer than `SLOW_QUERY_SECONDS`. Then the panel ticks "Performance issue" in the `error_types` question. It also adds a line to the `notes` question.

## Settings

| Variable | Meaning |
| --- | --- |
| `ARGILLA_QUESTDB_URL` | QuestDB HTTP address, as seen from the Argilla container. If it is not set, the endpoint returns HTTP 503. |
| `ARGILLA_QUESTDB_TIMEOUT` | Seconds to wait for a query. The default is `60`. |
| `ARGILLA_QUESTDB_MAX_ROWS` | Max number of rows in a response. The default is `1000`. |
| `SLOW_QUERY_SECONDS` | Setup command only. Run time that flags a query. The default is `3`. |

## Setup command

The setup command does these steps for each dataset:

1. If the `sql` field is a text field and no record has annotations, the command copies the dataset into a new dataset with the panel. It adds the suffix `- archived` to the name of the old dataset.
2. If the `sql` field is a text field and some records have annotations, the command skips the dataset.
3. If the `sql` field is already the panel, the command writes the current panel and `SLOW_QUERY_SECONDS` into it.
4. If you give `--backup <file>`, the command creates each dataset in the file that does not exist on the server.

## Build

Run this command from the `argilla-server` folder:

```
docker buildx build --platform linux/amd64 -f docker/sql-review/Dockerfile -t botsync/argilla-custom:1.0.0 .
```

## Run

1. Copy `docker-compose.yaml` and `.env.example` to the server.
2. Rename `.env.example` to `.env` and set `QUESTDB_URL`.
3. To keep the data of an existing deployment, set `name:` in `docker-compose.yaml` to the project name of that deployment.
4. Start the services:

```
docker compose up -d
docker compose logs sql-review-setup
```
