from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct

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
    stmt = (
        select(
            GenreModel.id,
            GenreModel.name,
            func.count(distinct(MovieModel.id)).label("movie_count"),
            func.array_agg(distinct(MovieModel.id)).label("movie_ids")
        )
        .outerjoin(GenreModel.movies)
        .group_by(GenreModel.id, GenreModel.name)
        .order_by(GenreModel.name)
    )

    result = await db.execute(stmt)
    genres_data = result.all()

    return [
        GenreReadSchema(
            id=genre_id,
            name=name,
            movie_count=movie_count,
            movie_ids=movie_ids if movie_ids[0] is not None else []
        )
        for genre_id, name, movie_count, movie_ids in genres_data
    ]


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
