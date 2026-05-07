
# # import os
# # import multiprocessing as mp
# # try:
# #     mp.set_start_method('spawn', force=True)
# # except RuntimeError:
# #     pass

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import synthesis
from app.api.endpoints import style_analysis
from app.models_svc.stylesinger_wrapper import stylesinger_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.enhanced_stack_status = stylesinger_service.get_enhanced_stack_status(force_refresh=True)
    yield

app = FastAPI(
    title="Singing Voice Style Conversion API",
    description="Hybrid singing voice conversion API with So-VITS-SVC as the default pipeline and StyleSinger as advanced mode",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(synthesis.router, prefix="/api/v1", tags=["synthesis"])
app.include_router(style_analysis.router, prefix="/api/v1", tags=["style-analysis"])

@app.get("/")
async def root():
    return {"message": "Welcome to Singing Voice Style Conversion System"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
