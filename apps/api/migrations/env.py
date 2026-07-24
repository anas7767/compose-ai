from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from compose_ai_api.core.config import get_settings
from compose_ai_api.domains.ai_architect import models as ai_architect_models  # noqa: F401
from compose_ai_api.domains.billing import models as billing_models  # noqa: F401
from compose_ai_api.domains.building_visualization import (  # noqa: F401
    models as building_visualization_models,
)
from compose_ai_api.domains.exterior_design import models as exterior_design_models  # noqa: F401
from compose_ai_api.domains.floor_plan_editor import models as floor_plan_editor_models  # noqa: F401
from compose_ai_api.domains.floor_plans import models as floor_plan_models  # noqa: F401
from compose_ai_api.domains.identity import models as identity_models  # noqa: F401
from compose_ai_api.domains.infrastructure import models as infrastructure_models  # noqa: F401
from compose_ai_api.domains.plot_intelligence import models as plot_models  # noqa: F401
from compose_ai_api.domains.projects import models as project_models  # noqa: F401
from compose_ai_api.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
