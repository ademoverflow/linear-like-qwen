import uvicorn

from core.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "core.main:app",
        host=settings.core_server_host,
        port=settings.core_server_port,
        reload=settings.dev_mode,
    )
