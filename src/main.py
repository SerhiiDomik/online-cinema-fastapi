from fastapi import FastAPI

from routes import (
    users_router,
)

app = FastAPI(
    title="Online Cinema API",
    description="API for managing movies and user accounts",
    version="0.1.0"
)

app.include_router(users_router, prefix=f"/users", tags=["users"])
