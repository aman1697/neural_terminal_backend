from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.rate_limit import limit_by_ip, parse_limit
from api.routes import auth, learning, users
from config.settings import settings
from src.helpers import paths_store

app = FastAPI(
	dependencies=[Depends(limit_by_ip("global", parse_limit(settings.rate_limit_default)))],
)


# TODO(production): origins come from CORS_ALLOWED_ORIGINS in .env; update it for the deployed frontend.
app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origins,
	allow_credentials=True,
	allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
	allow_headers=["Authorization", "Content-Type"],
	expose_headers=["Retry-After"],
)


@app.get("/paths")
async def get_paths(refresh: bool = False):
	return await paths_store.load_all(refresh)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(learning.router)
