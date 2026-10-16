"""The migrations build the schema the models declare, so a deploy that runs
`alembic upgrade head` gets the same tables the app expects."""
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from conftest import ROOT


@pytest.fixture(params=["sqlite", "postgres"])
def fresh_database_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite+pysqlite:///{tmp_path}/fresh.db"
        return

    server_url = os.environ.get("TEST_POSTGRES_URL")
    if not server_url:
        pytest.skip("TEST_POSTGRES_URL is not set")
    name = f"solna_migrations_{uuid.uuid4().hex}"
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(server_url).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_a_fresh_database_upgraded_to_head_matches_the_models(fresh_database_url):
    env = {**os.environ, "DATABASE_URL": fresh_database_url}

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=ROOT / "api", env=env, check=True
        )

    alembic("upgrade", "head")
    alembic("check")
