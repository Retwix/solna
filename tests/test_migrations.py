"""The migrations build the schema the models declare, so a deploy that runs
`alembic upgrade head` gets the same tables the app expects."""
import os
import subprocess
import sys

from conftest import ROOT


def test_a_fresh_database_upgraded_to_head_matches_the_models(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path}/fresh.db"}

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=ROOT / "api", env=env, check=True
        )

    alembic("upgrade", "head")
    alembic("check")
