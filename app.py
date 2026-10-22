import uvicorn
import sys
import os

# Ensure current folder is in Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings

if __name__ == "__main__":
    print("============================================================")
    print(f"[HOSPITAL] {settings.HOSPITAL_NAME}")
    print(f"[SYSTEM]   City Hospital Enterprise HMS v{settings.VERSION}")
    print(f"[SERVER]   Serving Live on: http://localhost:{settings.PORT}")
    print(f"[SWAGGER]  Interactive OpenAPI Docs: http://localhost:{settings.PORT}/docs")
    print("============================================================")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.RELOAD)
