import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.equipment import router as equipment_router
from app.api.equipment_detail import router as equipment_detail_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.maintenance import router as maintenance_router
from app.api.predictions import router as predictions_router
from app.api.realtime import realtime_manager, router as realtime_router
from app.api.reports import router as reports_router
from app.api.simulation import router as simulation_router
from app.api.work_orders import router as work_orders_router
from app.core.config import get_settings
from app.services.realtime_loop import run_realtime_loop


def create_app(enable_realtime: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=_realtime_lifespan if enable_realtime else None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(equipment_router)
    app.include_router(equipment_detail_router)
    app.include_router(work_orders_router)
    app.include_router(knowledge_router)
    app.include_router(maintenance_router)
    app.include_router(reports_router)
    app.include_router(predictions_router)
    app.include_router(simulation_router)
    app.include_router(realtime_router)
    return app


@asynccontextmanager
async def _realtime_lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_realtime_loop(realtime_manager, stop_event))
    app.state.realtime_stop_event = stop_event
    app.state.realtime_task = task

    try:
        yield
    finally:
        stop_event.set()
        with suppress(asyncio.CancelledError):
            await task


app = create_app()
