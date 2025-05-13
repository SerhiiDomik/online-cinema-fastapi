from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from database.models import GenreModel
from schemas.movies import GenreSchema

router = APIRouter()


@router.get("/", response_model=List[GenreSchema])
async def get_genres(db: AsyncSession = Depends(get_db)):
    stmt = select(GenreModel).options(selectinload(GenreModel.movies))
    result = await db.execute(stmt)
    genres = result.scalars().all()
    return [GenreSchema(
        id=genre.id,
        name=genre.name,
        movie_count=len(genre.movies)
    ) for genre in genres]


@router.post("/", response_model=GenreSchema)
async def create_genre(name: str, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(GenreModel).where(GenreModel.name == name))
    if existing.scalar():
        raise HTTPException(400, "Genre already exists")

    genre = GenreModel(name=name)
    db.add(genre)
    await db.commit()
    return genre
