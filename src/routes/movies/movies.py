import uuid
from collections import defaultdict
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from sqlalchemy import select, func, or_, and_, distinct
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional

from database import get_db, User
from database.models import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from database.models.movies import CommentModel, MovieRatingModel, MovieReactionModel, ReactionEnum
from routes.dependencies import get_current_user, parse_comment_with_replies_model
from schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    CommentSchema,
    CommentCreate,
    RatingRequest,
    ReactionRequest,
)

security = HTTPBearer()

router = APIRouter()


@router.get(
    "/",
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
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        year: int = None,
        min_rating: float = Query(None, ge=0, le=10),
        max_rating: float = Query(None, ge=0, le=10),
        genre: Optional[List[str]] = Query(
            default=None,
            description="List of genres, e.g., genre=Action&genre=Drama"
        ),
        certification: str = None,
        sort_by: str = Query(None, description="Sort by: price, year, imdb, votes"),
        search: str = None,
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    stmt = select(MovieModel).distinct()

    if year:
        stmt = stmt.where(MovieModel.year == int(year))

    if min_rating is not None:
        stmt = stmt.where(MovieModel.imdb >= min_rating)

    if max_rating is not None:
        stmt = stmt.where(MovieModel.imdb <= max_rating)

    if genre:
        stmt = stmt.join(MovieModel.genres).group_by(MovieModel.id).having(
            func.count(distinct(GenreModel.name)).filter(GenreModel.name.in_(genre)) == len(genre)
        )

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
        stmt = stmt.order_by(MovieModel.id.desc())

    stmt = stmt.options(
        joinedload(MovieModel.certification),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars)
    )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_items = (await db.execute(count_stmt)).scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    paginated_stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(paginated_stmt)
    movies = result.unique().scalars().all()

    total_pages = (total_items + per_page - 1) // per_page

    if page > total_pages != 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    return MovieListResponseSchema(
        movies=[MovieListItemSchema.model_validate(movie, from_attributes=True) for movie in movies],
        total_items=total_items,
        total_pages=total_pages,
        prev_page=f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        current_page=page
    )


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    dependencies=[Depends(security)],
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

        stmt = (
            select(MovieModel)
            .where(MovieModel.id == movie.id)
            .options(
                selectinload(MovieModel.genres),
                selectinload(MovieModel.directors),
                selectinload(MovieModel.stars),
                selectinload(MovieModel.certification),
                selectinload(MovieModel.comments).joinedload(CommentModel.user),
            )
        )
        result = await db.execute(stmt)
        movie_with_relations = result.scalar_one()

        return MovieDetailSchema.model_validate(movie_with_relations, from_attributes=True)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid input data."
        )


@router.get(
    "/{movie_id}/",
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
            selectinload(MovieModel.comments)
            .joinedload(CommentModel.user),
            selectinload(MovieModel.comments)
            .selectinload(CommentModel.replies)
            .joinedload(CommentModel.user),
            selectinload(MovieModel.comments)
            .selectinload(CommentModel.reactions),
            selectinload(MovieModel.reactions),
            selectinload(MovieModel.ratings)
        )
    )

    movie = result.unique().scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    likes_count = len([r for r in movie.reactions if r.reaction == ReactionEnum.LIKE])
    dislikes_count = len([r for r in movie.reactions if r.reaction == ReactionEnum.DISLIKE])

    avg_rating = sum(r.rating for r in movie.ratings) / len(movie.ratings) if movie.ratings else None

    comments_data = [
        parse_comment_with_replies_model(comment)
        for comment in movie.comments
        if comment.parent_id is None
    ]

    movie_data = movie.__dict__.copy()
    movie_data.pop("comments", None)
    movie_data.pop("_sa_instance_state", None)

    return MovieDetailSchema(
        **movie_data,
        likes_count=likes_count,
        dislikes_count=dislikes_count,
        average_rating=round(avg_rating, 1) if avg_rating else None,
        comments=comments_data
    )


@router.delete(
    "/{movie_id}/",
    summary="Delete a movie by ID",
    dependencies=[Depends(security)],
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
    "/{movie_id}/",
    summary="Update a movie by ID",
    dependencies=[Depends(security)],
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
            selectinload(MovieModel.stars),
            selectinload(MovieModel.certification),
            selectinload(MovieModel.comments)
            .selectinload(CommentModel.user),
            selectinload(MovieModel.comments)
            .selectinload(CommentModel.replies)
            .selectinload(CommentModel.user),
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

    return MovieDetailSchema.model_validate(movie, from_attributes=True)


@router.post(
    "/{movie_id}/comments/",
    response_model=CommentSchema,
    dependencies=[Depends(security)],
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
        await db.refresh(comment, ["user", "replies", "reactions"])

        if not comment.user:
            comment.user = current_user
        comment.user_email = current_user.email

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error to create comment"
        )

    comment.user_email = current_user.email
    return comment


@router.get(
    "/{movie_id}/comments/",
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
@router.get(
    "/{movie_id}/comments/",
    response_model=list[CommentSchema],
    operation_id="get_movie_comments",
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
        .options(
            joinedload(CommentModel.user),
            selectinload(CommentModel.reactions)
        )
    )

    comments = result.unique().scalars().all()

    comment_dict = defaultdict(list)
    id_to_comment = {}
    for comment in comments:
        comment_dict[comment.parent_id].append(comment.id)
        id_to_comment[comment.id] = {
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user_id": comment.user_id,
            "movie_id": comment.movie_id,
            "parent_id": comment.parent_id,
            "user_email": comment.user.email,
            "likes_count": sum(1 for r in comment.reactions if r.reaction == ReactionEnum.LIKE),
            "dislikes_count": sum(1 for r in comment.reactions if r.reaction == ReactionEnum.DISLIKE),
            "replies": []
        }

    def build_comment_tree(parent_id=None):
        tree = []
        for comment_id in comment_dict.get(parent_id, []):
            comment_data = id_to_comment[comment_id]
            comment_data["replies"] = build_comment_tree(comment_id)
            tree.append(comment_data)
        return tree

    comment_tree = build_comment_tree()

    return comment_tree


@router.post(
    "/{movie_id}/reaction/",
    dependencies=[Depends(security)],
    status_code=status.HTTP_200_OK
)
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


@router.post(
    "/{movie_id}/rate/",
    dependencies=[Depends(security)],
    status_code=status.HTTP_200_OK
)
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
