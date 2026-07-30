from __future__ import annotations

from contextlib import asynccontextmanager

from .main import app, require_gateway_auth, settings
from .object_api import build_object_router
from .object_config import get_object_settings
from .object_store import S3ObjectStore
from .objects import ObjectRegistry

object_settings = get_object_settings()
_base_lifespan = app.router.lifespan_context


@asynccontextmanager
async def application_lifespan(application):
    async with _base_lifespan(application):
        if object_settings.object_api_enabled:
            application.state.objects = ObjectRegistry(
                object_settings.object_registry_path,
                object_settings.object_max_size_bytes,
            )
            await application.state.objects.initialize()
            application.state.object_store = S3ObjectStore(object_settings)
        yield


app.router.lifespan_context = application_lifespan
app.include_router(
    build_object_router(
        settings,
        object_settings,
        require_gateway_auth,
    )
)
