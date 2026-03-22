from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.models.notification import Base as NotificationBase
from app.models.template import Base as TemplateBase
from app.models.preference import Base as PreferenceBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine all model metadata so autogenerate sees all tables
from app.models.base import Base
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = settings.database_url.replace("asyncpg", "psycopg2")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    url = settings.database_url.replace("asyncpg", "psycopg2")
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()