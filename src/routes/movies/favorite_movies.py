from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from config.dependencies import get_current_user
from database import get_db, User
from database.models import MovieModel, GenreModel, CertificationModel, DirectorModel, StarModel
from database.models.movies import FavoriteMoviesModel
from schemas.movies import FavoriteListResponseSchema, FavoriteMovieSchema

router = APIRouter()


@router.post(
    "/{movie_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Add movie to favorites"
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
                FavoriteMoviesModel.movie_id == movie_id
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
    "/{movie_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove movie from favorites"
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
                FavoriteMoviesModel.movie_id == movie_id
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
    summary="Get favorite movies"
)
async def get_favorites(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        year: int = None,
        min_rating: float = Query(None, ge=0, le=10),
        max_rating: float = Query(None, ge=0, le=10),
        genre: str = None,
        certification: str = None,
        sort_by: str = Query(None),
        search: str = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    stmt = (
        select(MovieModel)
        .join(FavoriteMoviesModel)
        .where(FavoriteMoviesModel.user_id == current_user.id)
    )

    if year:
        stmt = stmt.where(MovieModel.year == year)

    if min_rating is not None:
        stmt = stmt.where(MovieModel.imdb >= min_rating)

    if max_rating is not None:
        stmt = stmt.where(MovieModel.imdb <= max_rating)

    if genre:
        stmt = stmt.join(MovieModel.genres).where(GenreModel.name == genre)

    if certification:
        stmt = stmt.join(MovieModel.certification).where(CertificationModel.name == certification)

    if search:
        stmt = stmt.join(MovieModel.directors).join(MovieModel.stars).where(
            or_(
                MovieModel.name.ilike(f"%{search}%"),
                MovieModel.description.ilike(f"%{search}%"),
                DirectorModel.name.ilike(f"%{search}%"),
                StarModel.name.ilike(f"%{search}%")
            )
        )

    if sort_by:
        sort_mapping = {
            "price": MovieModel.price,
            "year": MovieModel.year,
            "imdb": MovieModel.imdb,
            "votes": MovieModel.votes,
            "favorited": FavoriteMoviesModel.created_at
        }
        sort_field = sort_mapping.get(sort_by.lstrip("-"))
        if sort_field is None:
            raise HTTPException(status_code=400, detail="Invalid sort_by parameter")

        if sort_by.startswith("-"):
            stmt = stmt.order_by(sort_field.desc())
        else:
            stmt = stmt.order_by(sort_field.asc())
    else:
        stmt = stmt.order_by(FavoriteMoviesModel.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt)
    total_items = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt.options(
        joinedload(MovieModel.certification),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars)
    ))
    movies = result.unique().scalars().all()

    return FavoriteListResponseSchema(
        movies=[FavoriteMovieSchema.model_validate(movie) for movie in movies],
        total_items=total_items,
        total_pages=(total_items + per_page - 1) // per_page,
        current_page=page
    )
