from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

from schemas.examples.movies import (
    certification_example,
    genre_example,
    star_example,
    director_example,
    movie_create_example,
    movie_list_item_example,
    movie_detail_example,
    movie_list_response_example,
    genre_list_example
)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentSchema(CommentCreate):
    id: int
    created_at: datetime
    user_id: int
    movie_id: int
    user_email: str
    parent_id: Optional[int] = None
    replies: List["CommentSchema"] = []
    likes_count: int = 0
    dislikes_count: int = 0

    class Config:
        from_attributes = True


class CommentReactionRequest(BaseModel):
    reaction: Optional[Literal["like", "dislike"]] = None


class ReactionRequest(BaseModel):
    reaction: Optional[Literal["like", "dislike"]] = None


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=10)


class CertificationSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
        json_schema_extra = {"example": certification_example}


class GenreSchema(BaseModel):
    id: int
    name: str
    movie_count: Optional[int] = None

    class Config:
        from_attributes = True
        json_schema_extra = {"example": genre_example}


class StarSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
        json_schema_extra = {"example": star_example}


class DirectorSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
        json_schema_extra = {"example": director_example}


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=1888, le=datetime.now().year + 1)
    time: int = Field(..., ge=1, description="Duration in minutes")
    imdb: float = Field(..., ge=0.0, le=10.0)
    votes: int = Field(..., ge=0)
    description: str
    price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)

    @field_validator("year")
    @classmethod
    def validate_year(cls, value):
        current_year = datetime.now().year
        if value > current_year + 1:
            raise ValueError(f"Year cannot be greater than {current_year + 1}")
        return value


class MovieCreateSchema(MovieBaseSchema):
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None, ge=0)
    certification: str
    genres: List[str]
    directors: List[str]
    stars: List[str]

    class Config:
        json_schema_extra = {"example": movie_create_example}


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    year: Optional[int] = Field(None, ge=1888, le=datetime.now().year + 1)
    time: Optional[int] = Field(None, ge=1)
    imdb: Optional[float] = Field(None, ge=0.0, le=10.0)
    votes: Optional[int] = Field(None, ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=2)
    certification: Optional[str] = None
    genres: Optional[List[str]] = None
    directors: Optional[List[str]] = None
    stars: Optional[List[str]] = None


class MovieListItemSchema(MovieBaseSchema):
    id: int
    uuid: str
    certification: CertificationSchema
    genres: List[GenreSchema]
    directors: List[DirectorSchema]
    stars: List[StarSchema]

    class Config:
        from_attributes = True
        json_schema_extra = {"example": movie_list_item_example}


class MovieDetailSchema(MovieListItemSchema):
    meta_score: Optional[float]
    gross: Optional[float]
    comments: list[CommentSchema]
    likes_count: int = 0
    dislikes_count: int = 0
    average_rating: Optional[float] = None

    class Config:
        json_schema_extra = {"example": movie_detail_example}


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    total_items: int
    total_pages: int
    current_page: int

    class Config:
        json_schema_extra = {"example": movie_list_response_example}


class GenreListSchema(BaseModel):
    genres: List[GenreSchema]
    total: int

    class Config:
        json_schema_extra = {"example": genre_list_example}


class FavoriteMovieSchema(MovieListItemSchema):
    favorited_at: datetime


class FavoriteListResponseSchema(BaseModel):
    movies: List[FavoriteMovieSchema]
    total_pages: int
    total_items: int
    current_page: int
