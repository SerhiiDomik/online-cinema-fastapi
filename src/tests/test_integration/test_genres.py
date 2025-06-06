import pytest
from sqlalchemy import select

from database.models import GenreModel


@pytest.mark.asyncio
async def test_get_genres_empty(client):
    response = await client.get("/genres/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_genre_success(client, db_session, create_activated_user_with_token):
    _, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": "Action"}

    response = await client.post("/genres/", json=payload, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Action"

    result = await db_session.execute(
        select(GenreModel).where(GenreModel.name == "Action")
    )
    genre = result.scalar_one_or_none()
    assert genre is not None
    assert genre.name == "Action"


@pytest.mark.asyncio
async def test_create_duplicate_genre_fails(client, create_activated_user_with_token):
    _, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": "Comedy"}

    response1 = await client.post("/genres/", json=payload, headers=headers)
    assert response1.status_code == 200

    response2 = await client.post("/genres/", json=payload, headers=headers)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "Genre already exists"


@pytest.mark.asyncio
async def test_get_genres_movie_count_and_movies_ids(client, create_movies):
    genre_name = "Drama"

    movies = await create_movies(3, genres="Drama")

    response = await client.get("/genres/")
    assert response.status_code == 200

    genres = response.json()
    assert isinstance(genres, list)

    genre = next((g for g in genres if g["name"] == genre_name), None)
    assert genre is not None, f"Genre '{genre_name}' not found in response"

    assert genre["movie_count"] == 3

    expected_ids = sorted([movie.id for movie in movies])
    response_ids = sorted(genre["movie_ids"])

    assert response_ids == expected_ids
