from logging.config import fileConfig

from alembic import context

import models  # noqa: F401  (register tables on Base)
from database import Base, engine

fileConfig(context.config.config_file_name)

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
