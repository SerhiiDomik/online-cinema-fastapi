from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from sqlalchemy import select, func, or_, and_, delete, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db, User
from database.models import (
    MovieModel,
    GenreModel,
    CertificationModel,
    DirectorModel,
    StarModel,
)
from database.models.movies import FavoriteMoviesModel
from routes.dependencies import get_current_user
from schemas.movies import FavoriteListResponseSchema, FavoriteMovieSchema
from typing import Optional

router = APIRouter()

security = HTTPBearer()


@router.post(
    "/{movie_id}/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(security)],
    summary="Add movie to favorites",
)
async def add_to_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    exists = await db.execute(
        select(FavoriteMoviesModel).where(
            and_(
                FavoriteMoviesModel.user_id == current_user.id,
                FavoriteMoviesModel.movie_id == movie_id,
            )
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Movie already in favorites")

    favorite = FavoriteMoviesModel(user_id=current_user.id, movie_id=movie_id)
    db.add(favorite)
    await db.commit()

    return {"detail": "Movie added to favorites"}


@router.delete(
    "/{movie_id}/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(security)],
    summary="Remove movie from favorites",
)
async def remove_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(FavoriteMoviesModel).where(
            and_(
                FavoriteMoviesModel.user_id == current_user.id,
                FavoriteMoviesModel.movie_id == movie_id,
            )
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Movie not found in favorites")

    await db.commit()
    return {"detail": "Movie removed from favorites"}


@router.get(
    "/",
    response_model=FavoriteListResponseSchema,
    dependencies=[Depends(security)],
    summary="Get favorite movies",
)
async def get_favorites(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    year: int = None,
    min_rating: float = Query(None, ge=0, le=10),
    max_rating: float = Query(None, ge=0, le=10),
    genre: Optional[str] = Query(None),
    certification: str = None,
    sort_by: str = Query(
        None, description="Sort by: price, year, imdb, votes, favorited"
    ),
    search: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(MovieModel, FavoriteMoviesModel.created_at.label("favorited_at"))
        .join(FavoriteMoviesModel)
        .where(FavoriteMoviesModel.user_id == current_user.id)
        .distinct()
    )

    if year:
        stmt = stmt.where(MovieModel.year == int(year))

    if min_rating is not None:
        stmt = stmt.where(MovieModel.imdb >= min_rating)

    if max_rating is not None:
        stmt = stmt.where(MovieModel.imdb <= max_rating)

    if genre:
        genre_names = [name.strip() for name in genre.split(",")]
        genre_names = list(set(genre_names))

        stmt = (
            stmt.join(MovieModel.genres)
            .where(GenreModel.name.in_(genre_names))
            .group_by(MovieModel.id)
            .having(func.count(distinct(GenreModel.name)) == len(genre_names))
        )

    if certification:
        stmt = stmt.join(MovieModel.certification).where(
            CertificationModel.name == certification
        )

    if search:
        stmt = (
            stmt.join(MovieModel.directors)
            .join(MovieModel.stars)
            .where(
                or_(
                    MovieModel.name.ilike(f"%{search}%"),
                    MovieModel.description.ilike(f"%{search}%"),
                    DirectorModel.name.ilike(f"%{search}%"),
                    StarModel.name.ilike(f"%{search}%"),
                )
            )
        )

    if sort_by:
        sort_mapping = {
            "price": MovieModel.price,
            "year": MovieModel.year,
            "imdb": MovieModel.imdb,
            "votes": MovieModel.votes,
            "favorited": FavoriteMoviesModel.created_at,
        }
        sort_field = sort_mapping.get(sort_by.lstrip("-"))
        if sort_field is None:
            raise HTTPException(status_code=400, detail="Invalid sort_by parameter")

        stmt = stmt.order_by(
            sort_field.desc() if sort_by.startswith("-") else sort_field.asc()
        )
    else:
        stmt = stmt.order_by(FavoriteMoviesModel.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = (await db.execute(count_stmt)).scalar() or 0
    total_pages = (total_items + per_page - 1) // per_page

    if page > total_pages > 0:
        raise HTTPException(status_code=404, detail="Page not found")

    stmt = (
        stmt.options(
            joinedload(MovieModel.certification),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.stars),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    movies_with_dates = result.unique().tuples().all()

    return FavoriteListResponseSchema(
        movies=[
            FavoriteMovieSchema(**movie[0].__dict__, favorited_at=movie[1])
            for movie in movies_with_dates
        ],
        total_items=total_items,
        total_pages=total_pages,
        current_page=page,
    )
