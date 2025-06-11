import pytest
from httpx import AsyncClient
from decimal import Decimal


@pytest.mark.asyncio
async def test_add_movie_to_favorites_success(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    response = await client.post(
        f"/favorite-movies/{movie.id}/", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    assert response.json() == {"detail": "Movie added to favorites"}


@pytest.mark.asyncio
async def test_add_nonexistent_movie(client, create_activated_user_with_token):
    _, token = await create_activated_user_with_token()

    response = await client.post(
        f"/favorite-movies/99999/", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found"


@pytest.mark.asyncio
async def test_add_duplicate_movie(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    await client.post(
        f"/favorite-movies/{movie.id}/", headers={"Authorization": f"Bearer {token}"}
    )

    response = await client.post(
        f"/favorite-movies/{movie.id}/", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Movie already in favorites"


@pytest.mark.asyncio
async def test_remove_movie_from_favorites_success(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(f"/favorite-movies/{movie.id}/", headers=headers)

    response = await client.delete(f"/favorite-movies/{movie.id}/", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "Movie removed from favorites"}


@pytest.mark.asyncio
async def test_remove_movie_not_in_favorites(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/favorite-movies/{movie.id}/", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found in favorites"


@pytest.mark.asyncio
async def test_get_favorite_movies(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(2)
    headers = {"Authorization": f"Bearer {token}"}

    for movie in movies:
        await client.post(f"/favorite-movies/{movie.id}/", headers=headers)

    response = await client.get("/favorite-movies/", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "movies" in data
    assert isinstance(data["movies"], list)
    assert len(data["movies"]) == 2


@pytest.mark.asyncio
async def test_favorite_movies_pagination(
    client, db_session, create_movies, create_activated_user_with_token
):
    user, token = await create_activated_user_with_token()
    movies = await create_movies(15)

    for movie in movies:
        await client.post(
            f"/favorite-movies/{movie.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

    page, per_page = 2, 5
    resp = await client.get(
        f"/favorite-movies/?page={page}&per_page={per_page}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_items"] == 15
    assert data["total_pages"] == 3
    assert data["current_page"] == 2
    assert len(data["movies"]) == 5


@pytest.mark.asyncio
async def test_favorite_movies_filters(
    client, create_movies, create_activated_user_with_token
):
    user, token = await create_activated_user_with_token()

    movies = [
        (
            await create_movies(
                1,
                name="A",
                year=2020,
                imdb=8.0,
                genres=["Action"],
                certification_name="PG-13",
            )
        )[0],
        (
            await create_movies(
                1,
                name="B",
                year=2020,
                imdb=6.0,
                genres=["Drama"],
                certification_name="PG",
            )
        )[0],
        (
            await create_movies(
                1,
                name="C",
                year=2021,
                imdb=7.0,
                genres=["Action", "Sci-Fi"],
                certification_name="PG-13",
            )
        )[0],
    ]

    for movie in movies:
        await client.post(
            f"/favorite-movies/{movie.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/favorite-movies/?year=2020", headers={"Authorization": f"Bearer {token}"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 2
    assert all(m["year"] == 2020 for m in data["movies"])

    resp = await client.get(
        "/favorite-movies/?min_rating=7.0", headers={"Authorization": f"Bearer {token}"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 2
    assert all(m["imdb"] >= 7.0 for m in data["movies"])


@pytest.mark.asyncio
async def test_favorite_movies_sorting(
    client, create_movies, create_activated_user_with_token
):
    user, token = await create_activated_user_with_token()

    movies = [
        (
            await create_movies(
                1, name="X", price=Decimal("1.99"), year=2021, imdb=6.0, votes=100
            )
        )[0],
        (
            await create_movies(
                1, name="Y", price=Decimal("3.99"), year=2020, imdb=7.5, votes=300
            )
        )[0],
        (
            await create_movies(
                1, name="Z", price=Decimal("2.99"), year=2019, imdb=8.0, votes=200
            )
        )[0],
    ]

    for movie in movies:
        await client.post(
            f"/favorite-movies/{movie.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

    for field, expected_order in {
        "price": ["X", "Z", "Y"],
        "year": ["Z", "Y", "X"],
        "imdb": ["X", "Y", "Z"],
        "votes": ["X", "Z", "Y"],
    }.items():

        resp = await client.get(
            f"/favorite-movies/?sort_by={field}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        names = [m["name"] for m in resp.json()["movies"]]
        assert names == expected_order


@pytest.mark.asyncio
async def test_favorite_movies_search(
    client, create_movies, create_activated_user_with_token
):
    user, token = await create_activated_user_with_token()

    movies = [
        (
            await create_movies(
                1,
                name="The Matrix",
                directors=["Wachowski"],
                stars=["Keanu Reeves"],
                description="Deep thoughts",
            )
        )[0],
        (
            await create_movies(
                1,
                name="Interstellar",
                directors=["Christopher Nolan"],
                stars=["McConaughey"],
                description="Space travel",
            )
        )[0],
    ]
    for movie in movies:
        await client.post(
            f"/favorite-movies/{movie.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/favorite-movies/?search=Matrix", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["movies"][0]["name"] == "The Matrix"

    resp = await client.get(
        "/favorite-movies/?search=Nolan", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["movies"][0]["name"] == "Interstellar"


@pytest.mark.asyncio
async def test_favorite_movies_pagination_with_filters(
    client, create_movies, create_activated_user_with_token
):
    user, token = await create_activated_user_with_token()

    scifi_movies = await create_movies(
        15, year=2022, imdb=8.0, genres=["Sci-Fi"], certification_name="PG-13"
    )
    drama_movies = await create_movies(
        5, year=2021, imdb=6.0, genres=["Drama"], certification_name="PG"
    )

    for movie in scifi_movies + drama_movies:
        await client.post(
            f"/favorite-movies/{movie.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/favorite-movies/?page=1&per_page=10&year=2022&genre=Sci-Fi",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 15
    assert data["total_pages"] == 2
    assert len(data["movies"]) == 10

    resp = await client.get(
        "/favorite-movies/?page=2&per_page=10&year=2022&genre=Sci-Fi",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["movies"]) == 5

    resp = await client.get(
        "/favorite-movies/?page=3&per_page=10&year=2022&genre=Sci-Fi",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
