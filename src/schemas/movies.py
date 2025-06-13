from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from database.models.movies import ReactionEnum
from schemas.examples.movies import (
    certification_example,
    genre_example,
    star_example,
    director_example,
    movie_create_example,
    movie_list_item_example,
    movie_detail_example,
    movie_list_response_example,
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
    likes_count: int = 0
    dislikes_count: int = 0
    replies: List["CommentSchema"] = []

    class Config:
        from_attributes = True


class ReactionRequest(BaseModel):
    reaction: Optional[ReactionEnum] = None


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
    certification: Optional[CertificationSchema]
    genres: List[GenreSchema] = []
    directors: List[DirectorSchema] = []
    stars: List[StarSchema] = []

    class Config:
        from_attributes = True
        json_schema_extra = {"example": movie_list_item_example}


class MovieDetailSchema(MovieListItemSchema):
    meta_score: Optional[float]
    gross: Optional[float]
    comments: List[CommentSchema]
    likes_count: int = 0
    dislikes_count: int = 0
    average_rating: Optional[float] = None

    class Config:
        json_schema_extra = {"example": movie_detail_example}


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_items: int
    total_pages: int
    current_page: int

    class Config:
        json_schema_extra = {"example": movie_list_response_example}


class FavoriteMovieSchema(MovieListItemSchema):
    favorited_at: datetime


class FavoriteListResponseSchema(BaseModel):
    movies: List[FavoriteMovieSchema]
    total_pages: int
    total_items: int
    current_page: int


class GenreCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    class Config:
        json_schema_extra = {"example": {"name": "Action"}}


class GenreReadSchema(BaseModel):
    id: int
    name: str
    movie_count: int
    movie_ids: List[int]

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Action",
                "movie_count": 3,
                "movie_ids": [101, 102, 103],
            }
        }


CommentSchema.update_forward_refs()
