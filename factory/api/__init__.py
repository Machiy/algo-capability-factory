"""L5 接入层：FastAPI 服务与 OpenAPI 导出。"""

from factory.api.app import (
    CandidateSummary,
    RunRequest,
    RunResponse,
    create_app,
    write_openapi,
)

__all__ = [
    "CandidateSummary",
    "RunRequest",
    "RunResponse",
    "create_app",
    "write_openapi",
]
