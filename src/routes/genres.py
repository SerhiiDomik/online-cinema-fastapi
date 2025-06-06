from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

from database import get_db
from database.models import GenreModel, MovieModel
from schemas.movies import GenreReadSchema, GenreCreateSchema

router = APIRouter()

security = HTTPBearer()


@router.get(
    "/",
    response_model=List[GenreReadSchema]
)
async def get_genres(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GenreModel).options(selectinload(GenreModel.movies))
    )
    genres = result.scalars().all()

    response = []
    for genre in genres:
        movie_ids = [movie.id for movie in genre.movies] if genre.movies else []

        response.append(
            GenreReadSchema(
                id=genre.id,
                name=genre.name,
                movie_count=len(movie_ids),
                movie_ids=movie_ids,
            )
        )
    return response


@router.post(
    "/",
    response_model=GenreCreateSchema,
    dependencies=[Depends(security)],
)
async def create_genre(payload: GenreCreateSchema, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(GenreModel).where(GenreModel.name == payload.name))
    if existing.scalar():
        raise HTTPException(400, "Genre already exists")

    genre = GenreModel(name=payload.name)
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return genre
