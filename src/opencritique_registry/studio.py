from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI
from fastapi.responses import FileResponse

_STUDIO_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; frame-ancestors 'none'"
)

_STUDIO_SECURITY_HEADERS = {
    "Content-Security-Policy": _STUDIO_CSP,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


def _asset(name: str):
    return files("opencritique_registry").joinpath("studio_assets", name)


def install_studio_routes(app: FastAPI) -> None:
    @app.get("/studio", include_in_schema=False)
    def studio_index() -> FileResponse:
        return FileResponse(
            str(_asset("index.html")),
            media_type="text/html",
            headers=_STUDIO_SECURITY_HEADERS,
        )

    @app.get("/studio/app.js", include_in_schema=False)
    def studio_script() -> FileResponse:
        return FileResponse(
            str(_asset("app.js")),
            media_type="text/javascript",
            headers=_STUDIO_SECURITY_HEADERS,
        )

    @app.get("/studio/styles.css", include_in_schema=False)
    def studio_styles() -> FileResponse:
        return FileResponse(
            str(_asset("styles.css")),
            media_type="text/css",
            headers=_STUDIO_SECURITY_HEADERS,
        )
