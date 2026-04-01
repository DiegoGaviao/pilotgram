"""
CORS explícito: preflight OPTIONS + cabeçalhos em todas as respostas.

O CORSMiddleware do Starlette por vezes não cobre PUT/preflight ou respostas de erro
sem cabeçalhos — o browser mostra "No Access-Control-Allow-Origin" mesmo com allow_origins=['*'].
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Token Meta não circula no browser; * é aceitável para esta API.
_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


class PilotgramCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            h = dict(_CORS)
            req_headers = request.headers.get("access-control-request-headers")
            if req_headers:
                h["Access-Control-Allow-Headers"] = req_headers
            return Response(status_code=200, content=b"", headers=h)

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Request failed before response (CORS-wrapped 500)")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers=dict(_CORS),
            )

        for key, val in _CORS.items():
            if key == "Access-Control-Max-Age":
                continue
            response.headers.setdefault(key, val)
        return response
