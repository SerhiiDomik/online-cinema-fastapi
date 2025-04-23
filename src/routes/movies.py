import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from config.dependencies import get_current_user
from database import get_db, User
from database.models import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from database.models.movies import CommentModel, MovieRatingModel, MovieReactionModel, ReactionEnum, FavoriteMoviesModel
from schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema, CommentSchema, CommentCreate, RatingRequest, ReactionRequest, FavoriteListResponseSchema,
    FavoriteMovieSchema, GenreSchema
)
router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    responses={
        404: {
            "description": "No movies found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No movies found."}
                }
            },
        }
    }
)
async def get_movie_list(
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
        year: int = None,
        min_rating: float = Query(None, ge=0, le=10),
        max_rating: float = Query(None, ge=0, le=10),
        genre: str = None,
        certification: str = None,
        sort_by: str = Query(None, description="Sort by: price, year, imdb, votes"),
        search: str = None,
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    stmt = select(MovieModel).distinct()

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
            "votes": MovieModel.votes
        }
        sort_field = sort_mapping.get(sort_by.lstrip("-"))
        if sort_field is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid sort_by parameter"
            )

        if sort_by.startswith("-"):
            stmt = stmt.order_by(sort_field.desc())
        else:
            stmt = stmt.order_by(sort_field.asc())
    else:
        stmt = stmt.order_by(MovieModel.year.desc())

    count_stmt = select(func.count(MovieModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt.options(
        joinedload(MovieModel.certification),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars)
    ))
    movies = result.unique().scalars().all()

    response = MovieListResponseSchema(
        movies=[MovieListItemSchema.model_validate(movie) for movie in movies],
        prev_page=f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    responses={
        201: {
            "description": "Movie created successfully.",
        },
        400: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        }
    },
    status_code=201
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:

    existing = await db.execute(
        select(MovieModel).where(
            and_(
                MovieModel.name == movie_data.name,
                MovieModel.year == movie_data.year,
                MovieModel.time == movie_data.time
            )
        )
    )
    if existing.scalar():
        raise HTTPException(
            status_code=400,
            detail="Movie with these attributes already exists"
        )

    cert = await db.execute(
        select(CertificationModel).where(CertificationModel.name == movie_data.certification)
    )
    cert = cert.scalar_one_or_none()
    if not cert:
        cert = CertificationModel(name=movie_data.certification)
        db.add(cert)
        await db.flush()

    try:
        genres = []
        for genre_name in movie_data.genres:
            genre = await db.execute(select(GenreModel).where(GenreModel.name == genre_name))
            genre = genre.scalar_one_or_none()
            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        directors = []
        for director_name in movie_data.directors:
            director = await db.execute(select(DirectorModel).where(DirectorModel.name == director_name))
            director = director.scalar_one_or_none()
            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        stars = []
        for star_name in movie_data.stars:
            star = await db.execute(select(StarModel).where(StarModel.name == star_name))
            star = star.scalar_one_or_none()
            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        movie = MovieModel(
            uuid=str(uuid.uuid4()),
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification_id=cert.id,
            genres=genres,
            directors=directors,
            stars=stars
        )

        db.add(movie)
        await db.commit()
        await db.refresh(movie)
        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    }
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            joinedload(MovieModel.certification),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.comments).joinedload(CommentModel.user),
        )
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    for comment in movie.comments:
        comment.user_email = comment.user.email

    likes_result = await db.execute(
        select(func.count()).where(
            and_(
                MovieReactionModel.movie_id == movie_id,
                MovieReactionModel.reaction == ReactionEnum.LIKE
            )
        )
    )
    likes_count = likes_result.scalar() or 0

    dislikes_result = await db.execute(
        select(func.count()).where(
            and_(
                MovieReactionModel.movie_id == movie_id,
                MovieReactionModel.reaction == ReactionEnum.DISLIKE
            )
        )
    )
    dislikes_count = dislikes_result.scalar() or 0

    avg_rating_result = await db.execute(
        select(func.avg(MovieRatingModel.rating)).where(
            MovieRatingModel.movie_id == movie_id
        )
    )
    avg_rating = avg_rating_result.scalar()
    if avg_rating:
        avg_rating = round(float(avg_rating), 1)

    movie_detail = MovieDetailSchema.model_validate(movie)
    movie_detail.likes_count = likes_count
    movie_detail.dislikes_count = dislikes_count
    movie_detail.average_rating = avg_rating

    return movie_detail


@router.delete(
    "/movies/{movie_id}/",
    summary="Delete a movie by ID",
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):

    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully."}


@router.patch(
    "/movies/{movie_id}/",
    summary="Update a movie by ID",
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    }
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.stars)
        )
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        if field not in ["genres", "directors", "stars", "certification"]:
            setattr(movie, field, value)

    if movie_data.certification:
        cert = await db.execute(
            select(CertificationModel).where(CertificationModel.name == movie_data.certification))
        cert = cert.scalar_one_or_none()
        if not cert:
            cert = CertificationModel(name=movie_data.certification)
            db.add(cert)
            await db.flush()
        movie.certification_id = cert.id

    if movie_data.genres is not None:
        new_genres = []
        for genre_name in movie_data.genres:
            genre = await db.execute(select(GenreModel).where(GenreModel.name == genre_name))
            genre = genre.scalar_one_or_none()
            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            new_genres.append(genre)
        movie.genres = new_genres

    if movie_data.directors is not None:
        new_directors = []
        for director_name in movie_data.directors:
            director = await db.execute(select(DirectorModel).where(DirectorModel.name == director_name))
            director = director.scalar_one_or_none()
            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            new_directors.append(director)
        movie.directors = new_directors

    if movie_data.stars is not None:
        new_stars = []
        for star_name in movie_data.stars:
            star = await db.execute(select(StarModel).where(StarModel.name == star_name))
            star = star.scalar_one_or_none()
            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                await db.flush()
            new_stars.append(star)
        movie.stars = new_stars

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return MovieDetailSchema.model_validate(movie)


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": "Comment created successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Comment created successfully."}
                }
            },
        },
    }
)
async def create_comment(
        movie_id: int,
        comment_data: CommentCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movies not found"
        )

    comment = CommentModel(
        content=comment_data.content,
        user_id=current_user.id,
        movie_id=movie_id
    )

    try:
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error to create comment"
        )

    comment.user_email = current_user.email
    return comment


@router.get(
    "/movies/{movie_id}/comments",
    response_model=list[CommentSchema],
    responses={
        404: {
            "description": "Comment not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Comments with the given ID was not found."}
                }
            },
        }
    }
)
async def get_comments(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CommentModel)
        .where(CommentModel.movie_id == movie_id)
        .options(joinedload(CommentModel.user))
        .order_by(CommentModel.created_at.desc())
    )
    comments = result.scalars().all()

    for comment in comments:
        comment.user_email = comment.user.email
    return comments


@router.post("/movies/{movie_id}/reaction", status_code=status.HTTP_200_OK)
async def set_movie_reaction(
    movie_id: int,
    reaction_data: ReactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    reaction = reaction_data.reaction

    existing_reaction = await db.execute(
        select(MovieReactionModel).where(
            and_(
                MovieReactionModel.user_id == current_user.id,
                MovieReactionModel.movie_id == movie_id
            )
        )
    )
    existing_reaction = existing_reaction.scalar_one_or_none()

    if reaction is None:
        if existing_reaction:
            await db.delete(existing_reaction)
            await db.commit()
        return {"detail": "Reaction removed"}
    else:
        if existing_reaction:
            existing_reaction.reaction = reaction
        else:
            new_reaction = MovieReactionModel(
                user_id=current_user.id,
                movie_id=movie_id,
                reaction=reaction
            )
            db.add(new_reaction)
        await db.commit()
    return {"detail": "Reaction updated"}


@router.post("/movies/{movie_id}/rate", status_code=status.HTTP_200_OK)
async def rate_movie(
    movie_id: int,
    rating_data: RatingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    existing_rating = await db.execute(
        select(MovieRatingModel).where(
            and_(
                MovieRatingModel.user_id == current_user.id,
                MovieRatingModel.movie_id == movie_id
            )
        )
    )
    existing_rating = existing_rating.scalar_one_or_none()

    if existing_rating:
        existing_rating.rating = rating_data.rating
    else:
        new_rating = MovieRatingModel(
            user_id=current_user.id,
            movie_id=movie_id,
            rating=rating_data.rating
        )
        db.add(new_rating)
    await db.commit()
    return {"detail": "Rating updated"}


@router.post(
    "/movies/favorites/{movie_id}",
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
    "/movies/favorites/{movie_id}",
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
    "/movies/favorites/",
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

    # Сортування
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

    # Пагінація
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


@router.get("/genres/", response_model=List[GenreSchema])
async def get_genres(db: AsyncSession = Depends(get_db)):
    stmt = select(GenreModel).options(selectinload(GenreModel.movies))
    result = await db.execute(stmt)
    genres = result.scalars().all()
    return [GenreSchema(
        id=genre.id,
        name=genre.name,
        movie_count=len(genre.movies)
    ) for genre in genres]


@router.post("/genres/", response_model=GenreSchema)
async def create_genre(name: str, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(GenreModel).where(GenreModel.name == name))
    if existing.scalar():
        raise HTTPException(400, "Genre already exists")

    genre = GenreModel(name=name)
    db.add(genre)
    await db.commit()
    return genre

