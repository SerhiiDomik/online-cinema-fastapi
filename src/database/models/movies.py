from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    String,
    Float,
    Text,
    DECIMAL,
    UniqueConstraint,
    ForeignKey,
    Table,
    Column,
    func,
    DateTime,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database.models.base import Base
from database.models.users import User


class ReactionEnum(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"


MoviesGenresModel = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

MovieDirectorsModel = Table(
    "movie_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

MovieStarsModel = Table(
    "movie_stars",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "star_id",
        ForeignKey("stars.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


class FavoriteMoviesModel(Base):
    __tablename__ = "favorite_movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_user_movie_favorite"),
    )

    user: Mapped["User"] = relationship(back_populates="favorite_movies")
    movie: Mapped["MovieModel"] = relationship(back_populates="favorited_by_users")


class MovieReactionModel(Base):
    __tablename__ = "movie_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    reaction: Mapped[ReactionEnum] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_user_movie_reaction"),
    )

    user: Mapped["User"] = relationship(back_populates="reactions")
    movie: Mapped["MovieModel"] = relationship(back_populates="reactions")


class MovieRatingModel(Base):
    __tablename__ = "movie_ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_user_movie_rating"),
    )

    user: Mapped["User"] = relationship(back_populates="ratings")
    movie: Mapped["MovieModel"] = relationship(back_populates="ratings")


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel", secondary=MoviesGenresModel, back_populates="genres"
    )

    def __repr__(self):
        return f"<Genre(name='{self.name}')>"


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel", secondary=MovieStarsModel, back_populates="stars"
    )

    def __repr__(self):
        return f"<Star(name='{self.name}')>"


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel", secondary=MovieDirectorsModel, back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel", back_populates="certification"
    )


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float)
    gross: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), nullable=False
    )
    comments: Mapped[list["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="movie",
        cascade="all, delete-orphan",
    )
    reactions: Mapped[list["MovieReactionModel"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )
    ratings: Mapped[list["MovieRatingModel"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )

    certification: Mapped["CertificationModel"] = relationship(
        "CertificationModel", back_populates="movies"
    )

    genres: Mapped[list["GenreModel"]] = relationship(
        "GenreModel", secondary=MoviesGenresModel, back_populates="movies"
    )

    directors: Mapped[list["DirectorModel"]] = relationship(
        "DirectorModel", secondary=MovieDirectorsModel, back_populates="movies"
    )

    stars: Mapped[list["StarModel"]] = relationship(
        "StarModel", secondary=MovieStarsModel, back_populates="movies"
    )

    favorited_by_users: Mapped[list["FavoriteMoviesModel"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="unique_movie_constraint"),
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self):
        return f"<Movie(name='{self.name}')>"


class CommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="comments", lazy="joined"
    )
    movie: Mapped["MovieModel"] = relationship(
        "MovieModel",
        back_populates="comments",
    )
    parent: Mapped[Optional["CommentModel"]] = relationship(
        back_populates="replies", remote_side=[id]
    )
    replies: Mapped[list["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="parent",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    reactions: Mapped[list["CommentReactionModel"]] = relationship(
        "CommentReactionModel",
        back_populates="comment",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class CommentReactionModel(Base):
    __tablename__ = "comment_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    reaction: Mapped[ReactionEnum] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="unique_user_comment_reaction"),
    )

    user: Mapped["User"] = relationship(back_populates="comment_reactions")
    comment: Mapped["CommentModel"] = relationship(back_populates="reactions")
