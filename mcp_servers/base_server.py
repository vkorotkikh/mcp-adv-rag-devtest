from fastapi import FastAPI


def create_app(title: str, version: str = "0.1.0") -> FastAPI:
    """Factory to build a FastAPI application with a standard /health route."""
    app = FastAPI(title=title, version=version)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": title, "version": version}

    return app
