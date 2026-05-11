
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
    title="歌声风格转换接口",
    description="以后端接口框架 FastAPI 提供的歌声风格转换接口，默认主链路为 So-VITS-SVC，StyleSinger 仅作为高级实验模式保留。",
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
    return {"message": "欢迎使用歌声风格转换系统"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
