from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from .admin_api import build_admin_router
from .admin_store import AdminStore
from .browser_memory import build_browser_memory_router
from .client_api import build_client_router
from .main import app, require_gateway_auth, settings
from .object_api import build_object_router
from .object_config import get_object_settings
from .object_reservations import ObjectReservationManager
from .object_store import S3ObjectStore
from .objects import ObjectRegistry

object_settings = get_object_settings()
_base_lifespan = app.router.lifespan_context


@asynccontextmanager
async def application_lifespan(application):
    cleanup_task: asyncio.Task[None] | None = None
    async with _base_lifespan(application):
        master_secret = os.getenv("SUMEME_ADMIN_MASTER_KEY", "").strip() or (
            settings.gateway_admin_token.get_secret_value()
        )
        application.state.admin_store = AdminStore(
            os.getenv("SUMEME_ADMIN_DB_PATH", "/data/gateway/admin.sqlite3"),
            master_secret=master_secret,
            lobe_database_url=os.getenv("LOBE_DATABASE_URL", ""),
        )
        await application.state.admin_store.initialize()

        if object_settings.object_api_enabled:
            application.state.objects = ObjectRegistry(
                object_settings.object_registry_path,
                object_settings.object_max_size_bytes,
            )
            await application.state.objects.initialize()
            application.state.object_store = S3ObjectStore(object_settings)
            application.state.object_reservations = ObjectReservationManager(
                registry=application.state.objects,
                store=application.state.object_store,
                registry_path=object_settings.object_registry_path,
                reservation_ttl_seconds=(
                    object_settings.object_reservation_ttl_seconds
                ),
                cleanup_interval_seconds=(
                    object_settings.object_cleanup_interval_seconds
                ),
                cleanup_batch_size=object_settings.object_cleanup_batch_size,
                operation_lease_seconds=(
                    object_settings.object_operation_lease_seconds
                ),
            )
            await application.state.object_reservations.initialize()
            cleanup_task = asyncio.create_task(
                application.state.object_reservations.run_forever(),
                name="sumeme-object-reservation-cleanup",
            )
        try:
            yield
        finally:
            if cleanup_task is not None:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task


app.router.lifespan_context = application_lifespan
app.include_router(
    build_object_router(
        settings,
        object_settings,
        require_gateway_auth,
    )
)
app.include_router(build_browser_memory_router(settings))
app.include_router(build_client_router())
app.include_router(build_admin_router())
