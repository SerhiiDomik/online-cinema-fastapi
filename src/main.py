from fastapi import FastAPI

from routes import (
    users_router,
    movies_router,
    favorites_router,
    genres_router,
    comments_router,
)

app = FastAPI(
    title="Online Cinema API",
    description="API for managing movies and user accounts",
    version="0.1.0",
)

app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(movies_router, prefix="/movies", tags=["movies"])
app.include_router(
    favorites_router, prefix="/favorite-movies", tags=["favorite-movies"]
)
app.include_router(genres_router, prefix="/genres", tags=["genres"])
app.include_router(comments_router)
