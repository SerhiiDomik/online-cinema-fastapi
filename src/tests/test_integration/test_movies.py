import random
from decimal import Decimal

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload

from database.models.movies import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CommentModel,
    MovieReactionModel,
    MovieRatingModel,
)


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    """
    Test that the `/movies/` endpoint returns a 404 error when the database is empty.
    """
    response = await client.get("/movies/")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    expected_detail = {"detail": "No movies found."}
    assert response.json() == expected_detail, f"Expected {expected_detail}, got {response.json()}"


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, create_movies):
    """
    Test the `/movies/` endpoint with default pagination parameters.
    """
    await create_movies(10)
    response = await client.get("/movies/")
    assert response.status_code == 200, "Expected status code 200, but got a different value"

    response_data = response.json()

    assert len(response_data["movies"]) == 10, "Expected 10 movies in the response, but got a different count"

    assert response_data["total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data["total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    assert response_data["prev_page"] is None, "Expected prev_page to be None on the first page, but got a value"

    if response_data["total_pages"] > 1:
        assert response_data["next_page"] is not None, (
            "Expected next_page to be present when total_pages > 1, but got None"
        )


@pytest.mark.asyncio
async def test_get_movies_with_custom_parameters(client, create_movies):
    """
    Test the `/movies/` endpoint with custom pagination parameters.
    """
    await create_movies(10)

    page = 2
    per_page = 5

    response = await client.get(f"/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert len(response_data["movies"]) == per_page, (
        f"Expected {per_page} movies in the response, but got {len(response_data['movies'])}"
    )

    assert response_data["total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data["total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    if page > 1:
        assert response_data["prev_page"] == f"/movies/?page={page - 1}&per_page={per_page}", (
            f"Expected prev_page to be '/movies/?page={page - 1}&per_page={per_page}', "
            f"but got {response_data['prev_page']}"
        )

    if page < response_data["total_pages"]:
        assert response_data["next_page"] == f"/movies/?page={page + 1}&per_page={per_page}", (
            f"Expected next_page to be '/movies/?page={page + 1}&per_page={per_page}', "
            f"but got {response_data['next_page']}"
        )
    else:
        assert response_data["next_page"] is None, "Expected next_page to be None on the last page, but got a value"


@pytest.mark.asyncio
@pytest.mark.parametrize("page, per_page, expected_detail", [
    (0, 10, "Input should be greater than or equal to 1"),
    (1, 0, "Input should be greater than or equal to 1"),
    (0, 0, "Input should be greater than or equal to 1"),
])
async def test_invalid_page_and_per_page(client, page, per_page, expected_detail, create_movies):
    """
    Test the `/movies/` endpoint with invalid `page` and `per_page` parameters.
    """
    await create_movies(10)

    response = await client.get(f"/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 422, (
        f"Expected status code 422 for invalid parameters, but got {response.status_code}"
    )

    response_data = response.json()

    assert "detail" in response_data, "Expected 'detail' in the response, but it was missing"

    assert any(expected_detail in error["msg"] for error in response_data["detail"]), (
        f"Expected error message '{expected_detail}' in the response details, but got {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_per_page_maximum_allowed_value(client, create_movies):
    """
    Test the `/movies/` endpoint with the maximum allowed `per_page` value.
    """
    await create_movies(10)

    response = await client.get("/movies/?page=1&per_page=20")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."
    assert len(response_data["movies"]) <= 20, (
        f"Expected at most 20 movies, but got {len(response_data['movies'])}"
    )


@pytest.mark.asyncio
async def test_page_exceeds_maximum(client, db_session, create_movies):
    """
    Test the `/movies/` endpoint with a page number that exceeds the maximum.
    """
    await create_movies(10)

    per_page = 10

    count_stmt = select(func.count(MovieModel.id))
    result = await db_session.execute(count_stmt)
    total_movies = result.scalar_one()

    max_page = (total_movies + per_page - 1) // per_page

    response = await client.get(f"/movies/?page={max_page + 1}&per_page={per_page}")

    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"
    response_data = response.json()

    assert "detail" in response_data, "Response missing 'detail' field."


@pytest.mark.asyncio
async def test_movies_sorted_by_id_desc(client, db_session, create_movies):
    """
    Test that movies are returned sorted by `id` in descending order
    and match the expected data from the database.
    """
    await create_movies(10)

    response = await client.get("/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `id` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movie_list_with_pagination(client, db_session, create_movies):
    """
    Test the `/movies/` endpoint with pagination parameters.

    Verifies the following:
    - The response status code is 200.
    - Total items and total pages match the expected values from the database.
    - The movies returned match the expected movies for the given page and per_page.
    - The `prev_page` and `next_page` links are correct.
    """
    await create_movies(10)

    page = 2
    per_page = 5
    offset = (page - 1) * per_page

    response = await client.get(f"/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    count_stmt = select(func.count(MovieModel.id))
    count_result = await db_session.execute(count_stmt)
    total_items = count_result.scalar_one()

    total_pages = (total_items + per_page - 1) // per_page

    assert response_data["total_items"] == total_items, "Total items mismatch."
    assert response_data["total_pages"] == total_pages, "Total pages mismatch."

    stmt = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert expected_movie_ids == returned_movie_ids, "Movies on the page mismatch."

    expected_prev_page = f"/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    expected_next_page = f"/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None

    assert response_data["prev_page"] == expected_prev_page, "Previous page link mismatch."
    assert response_data["next_page"] == expected_next_page, "Next page link mismatch."


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, create_movies):
    """
    Test that each movie in the response matches the fields defined in `MovieListItemSchema`.
    """
    await create_movies(10)

    response = await client.get("/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."

    expected_fields = {
        "id", "name", "uuid", "year", "time", "imdb", "votes", "price",
        "description", "certification", "genres", "directors", "stars"
    }

    for movie in response_data["movies"]:
        assert set(movie.keys()) == expected_fields, (
            f"Movie fields do not match schema. "
            f"Expected: {expected_fields}, but got: {set(movie.keys())}"
        )


@pytest.mark.asyncio
async def test_movie_filters(client, create_movies):
    await create_movies(1, year=2023, imdb=7.7, genres=["Action", "Drama"], certification_name="PG-13")
    await create_movies(1, year=2023, imdb=5.0, genres=["Comedy"], certification_name="PG-14")
    await create_movies(1, year=2021, imdb=7.7, genres=["Action", "Adventure"], certification_name="PG-15")
    await create_movies(1, year=2020, imdb=7.0, genres=["Drama", "Romance"], certification_name="PG-13")
    await create_movies(1, year=2019, imdb=8.0, genres=["Horror"], certification_name="PG-17")

    resp = await client.get("/movies/?year=2023")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 2
    assert all(m["year"] == 2023 for m in data["movies"])

    resp = await client.get("/movies/?min_rating=7.0&max_rating=8.5")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 4
    assert all(7.0 <= m["imdb"] <= 8.5 for m in data["movies"])

    resp = await client.get("/movies/?genre=Action")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 2
    assert all(any(g["name"] == "Action" for g in m["genres"]) for m in data["movies"])

    resp = await client.get("/movies/?genre=Action&genre=Drama")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 1
    assert all(
        any(g["name"] == "Action" for g in m["genres"]) and
        any(g["name"] == "Drama" for g in m["genres"])
        for m in data["movies"]
    )

    resp = await client.get("/movies/?certification=PG-13")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 2
    assert all(m["certification"]["name"] == "PG-13" for m in data["movies"])

    resp = await client.get("/movies/?year=2023&genre=Action&min_rating=7.0")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data["movies"]) == 1


@pytest.mark.asyncio
async def test_movie_sorting(client, create_movies):
    await create_movies(1, name="Movie A", price=Decimal("3.99"), year=2020, imdb=7.5, votes=100)
    await create_movies(1, name="Movie B", price=Decimal("1.99"), year=2021, imdb=6.0, votes=300)
    await create_movies(1, name="Movie C", price=Decimal("5.99"), year=2019, imdb=8.0, votes=200)

    async def get_names_by_sort(field: str):
        resp = await client.get(f"/movies/?sort_by={field}")
        assert resp.status_code == 200
        return [m["name"] for m in resp.json()["movies"]]

    names = await get_names_by_sort("price")
    assert names == ["Movie B", "Movie A", "Movie C"]

    names = await get_names_by_sort("year")
    assert names == ["Movie C", "Movie A", "Movie B"]

    names = await get_names_by_sort("imdb")
    assert names == ["Movie B", "Movie A", "Movie C"]

    names = await get_names_by_sort("votes")
    assert names == ["Movie A", "Movie C", "Movie B"]


@pytest.mark.asyncio
async def test_movie_search(client, create_movies):
    await create_movies(1, name="The Matrix", directors=["Lana Wachowski"], stars=["Keanu Reeves"], description="A film with deep emotions")
    await create_movies(1, name="Interstellar", directors=["Christopher Nolan"], stars=["Matthew McConaughey"], description="Explores deep emotions and space")
    await create_movies(1, name="Interstellar1", directors=["Christopher"], stars=["Matthew McConaughey"], description="Explores deep emotions and space")

    resp = await client.get("/movies/?search=Matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["movies"]) == 1
    assert data["movies"][0]["name"] == "The Matrix"

    resp = await client.get("/movies/?search=Nolan")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["movies"]) == 1
    assert data["movies"][0]["name"] == "Interstellar"

    resp = await client.get("/movies/?search=Reeves")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["movies"]) == 1
    assert data["movies"][0]["name"] == "The Matrix"

    resp = await client.get("/movies/?search=Explores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["movies"]) == 2


@pytest.mark.asyncio
async def test_movie_pagination_with_filters(client, create_movies):

    await create_movies(20, year=2022, imdb=8.0, genres=["Sci-Fi"], certification_name="PG-13")
    await create_movies(10, year=2021, imdb=7.0, genres=["Drama"], certification_name="R")

    resp = await client.get("/movies/?page=1&per_page=10&year=2022&min_rating=7.5&genre=Sci-Fi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 20
    assert data["total_pages"] == 2
    assert data["current_page"] == 1
    assert len(data["movies"]) == 10
    assert data["next_page"] is not None

    resp = await client.get("/movies/?page=2&per_page=10&year=2022&min_rating=7.5&genre=Sci-Fi")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["movies"]) == 10
    assert data["prev_page"] is not None
    assert data["next_page"] is None

    resp = await client.get("/movies/?page=3&per_page=10&year=2022&min_rating=7.5&genre=Sci-Fi")
    assert resp.status_code == 404

    resp = await client.get("/movies/?year=2021")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 10
    assert len(data["movies"]) == 10


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    """
    Test that the `/movies/{movie_id}` endpoint returns a 404 error
    when a movie with the given ID does not exist.
    """
    movie_id = 99999

    response = await client.get(f"/movies/{movie_id}/")
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    assert response_data == {"detail": "Movie not found"}, (
        f"Expected error message not found. Got: {response_data}"
    )


@pytest.mark.asyncio
async def test_get_movie_by_id_valid(client, db_session, create_movies):
    """
    Test that the `/movies/{movie_id}` endpoint returns the correct movie details
    when a valid movie ID is provided.

    Verifies the following:
    - The movie exists in the database.
    - The response status code is 200.
    - The movie's `id` and `name` in the response match the expected values from the database.
    """
    await create_movies(1)

    stmt = select(MovieModel.id).order_by(MovieModel.id.asc())
    result = await db_session.execute(stmt)
    all_ids = result.scalars().all()
    assert all_ids, "No movies found in the database."

    random_id = random.choice(all_ids)

    stmt_movie = select(MovieModel).where(MovieModel.id == random_id)
    result_movie = await db_session.execute(stmt_movie)
    expected_movie = result_movie.scalars().first()
    assert expected_movie is not None

    response = await client.get(f"/movies/{random_id}/")
    assert response.status_code == 200

    response_data = response.json()
    assert response_data["id"] == expected_movie.id
    assert response_data["name"] == expected_movie.name


@pytest.mark.asyncio
async def test_get_movie_by_id_fields_match_database(client, db_session, create_movies):
    """
    Test that the `/movies/{movie_id}` endpoint returns all fields matching the database data.
    """
    await create_movies(5)

    stmt = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.stars),
            joinedload(MovieModel.certification),
            selectinload(MovieModel.comments).joinedload(CommentModel.user),
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None

    response = await client.get(f"/movies/{movie.id}/")
    assert response.status_code == 200

    data = response.json()

    assert data["id"] == movie.id
    assert data["uuid"] == movie.uuid
    assert data["name"] == movie.name
    assert data["year"] == movie.year
    assert data["time"] == movie.time
    assert abs(data["imdb"] - movie.imdb) < 1e-5
    assert data["votes"] == movie.votes
    assert data["meta_score"] == movie.meta_score
    assert data["gross"] == movie.gross
    assert data["description"] == movie.description
    assert abs(Decimal(data["price"]) - movie.price) < Decimal("1e-5")

    assert data["certification"]["id"] == movie.certification.id
    assert data["certification"]["name"] == movie.certification.name

    # Genres
    expected_genres = sorted([g.name for g in movie.genres])
    response_genres = sorted([g["name"] for g in data["genres"]])
    assert response_genres == expected_genres

    # Directors
    expected_directors = sorted([d.name for d in movie.directors])
    response_directors = sorted([d["name"] for d in data["directors"]])
    assert response_directors == expected_directors

    # Stars
    expected_stars = sorted([s.name for s in movie.stars])
    response_stars = sorted([s["name"] for s in data["stars"]])
    assert response_stars == expected_stars

    for comment in data.get("comments", []):
        assert "id" in comment
        assert "text" in comment
        assert "user" in comment
        assert "id" in comment["user"]
        assert "username" in comment["user"]


async def test_create_movie_unauthorized(client):
    payload = {
        "name": "Unauthorized Movie",
        "year": 2025,
        "time": 90,
        "imdb": 7.0,
        "votes": 5000,
        "meta_score": 50,
        "gross": 250000,
        "description": "Unauthorized",
        "price": 5.0,
        "certification": "G",
        "genres": ["Horror"],
        "directors": ["Anon"],
        "stars": ["Unknown"]
    }

    response = await client.post(
        "/movies/",
        json=payload
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_movie_and_related_models(client, db_session, create_activated_user_with_token):
    """
    Test that a new movie is created successfully and related models
    (genres, actors, languages) are created if they do not exist.
    """

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    movie_data = {
        "name": "Inception",
        "year": 2010,
        "time": 148,
        "imdb": 8.8,
        "votes": 2000000,
        "meta_score": 74.0,
        "gross": 829895144.00,
        "description": "A thief who steals corporate secrets through dream-sharing technology is given a task.",
        "price": "14.99",
        "certification": "PG-13",
        "genres": ["Action", "Sci-Fi"],
        "directors": ["Christopher Nolan"],
        "stars": ["Leonardo DiCaprio", "Joseph Gordon-Levitt"]
    }

    response = await client.post("/movies/", json=movie_data, headers=headers)
    assert response.status_code == 201, response.text

    data = response.json()
    assert data["name"] == movie_data["name"]
    assert data["year"] == movie_data["year"]
    assert any(g["name"] == "Action" for g in data["genres"])
    assert any(d["name"] == "Christopher Nolan" for d in data["directors"])
    assert any(s["name"] == "Leonardo DiCaprio" for s in data["stars"])

    for genre_name in movie_data["genres"]:
        result = await db_session.execute(select(GenreModel).where(GenreModel.name == genre_name))
        genre = result.scalar_one_or_none()
        assert genre is not None, f"Genre '{genre_name}' should exist in DB"

    for director_name in movie_data["directors"]:
        result = await db_session.execute(select(DirectorModel).where(DirectorModel.name == director_name))
        director = result.scalar_one_or_none()
        assert director is not None, f"Director '{director_name}' should exist in DB"

    for star_name in movie_data["stars"]:
        result = await db_session.execute(select(StarModel).where(StarModel.name == star_name))
        star = result.scalar_one_or_none()
        assert star is not None, f"Star '{star_name}' should exist in DB"


@pytest.mark.asyncio
async def test_create_movie_duplicate_error(client, db_session, create_activated_user_with_token):
    """
    Test that trying to create a movie with the same name and date as an existing movie
    results in a 409 conflict error.
    """

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    movie_data = {
        "name": "The Matrix",
        "year": 1999,
        "time": 136,
        "imdb": 8.7,
        "votes": 1700000,
        "meta_score": 73.0,
        "gross": 463517383.00,
        "description": "A hacker discovers the true nature of reality.",
        "price": "12.99",
        "certification": "R",
        "genres": ["Action", "Sci-Fi"],
        "directors": ["The Wachowskis"],
        "stars": ["Keanu Reeves", "Carrie-Anne Moss"]
    }

    response1 = await client.post("/movies/", json=movie_data, headers=headers)
    assert response1.status_code == 201, response1.text

    response2 = await client.post("/movies/", json=movie_data, headers=headers)
    assert response2.status_code == 400, f"Expected 400, got {response2.status_code}"

    data = response2.json()
    assert "detail" in data
    assert data["detail"] == "Movie with these attributes already exists"


@pytest.mark.asyncio
async def test_delete_movie_success(client, db_session, create_movies, create_activated_user_with_token):
    """
    Test the `/movies/{movie_id}/` endpoint for successful movie deletion.
    """
    movies = await create_movies(1)
    movie_id  = movies[0].id

    user, access_token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.delete(f"/movies/{movie_id}/", headers=headers)
    assert response.status_code == 204, f"Expected status code 204, but got {response.status_code}"

    assert response.content == b"", "Response content should be empty for 204 No Content"

    stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
    result_check = await db_session.execute(stmt_check)
    deleted_movie = result_check.scalars().first()
    assert deleted_movie is None, f"Movie with ID {movie_id} was not deleted."


@pytest.mark.asyncio
async def test_delete_movie_not_found(client, create_activated_user_with_token):
    """
    Test the `/movies/{movie_id}/` endpoint with a non-existent movie ID.
    """
    non_existent_id = 99999

    user, access_token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.delete(f"/movies/{non_existent_id}/", headers=headers)
    assert response.status_code == 404, f"Expected status code 404, got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail


@pytest.mark.asyncio
async def test_update_movie_success(client, db_session, create_movies, create_activated_user_with_token):
    """
    Test the `/movies/{movie_id}/` endpoint for successfully updating a movie's details.
    """
    movies = await create_movies(1)
    movie_id = movies[0].id

    user, access_token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    update_data = {
        "name": "Updated Movie Name",
        "meta_score": 95.0,
    }

    response = await client.patch(f"/movies/{movie_id}/", json=update_data, headers=headers)
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    response_data = response.json()
    assert response_data["name"] == update_data["name"]
    assert response_data["meta_score"] == update_data["meta_score"]

    movie = await db_session.get(MovieModel, movie_id)
    await db_session.refresh(movie)

    assert movie.name == update_data["name"]
    assert movie.meta_score == update_data["meta_score"]


@pytest.mark.asyncio
async def test_update_movie_not_found(client, create_activated_user_with_token):
    """
    Test the `/movies/{movie_id}/` endpoint with a non-existent movie ID.
    """
    non_existent_id = 99999

    user, access_token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    update_data = {
        "name": "Non-existent Movie",
        "meta_score": 90.0,
    }

    response = await client.patch(f"/movies/{non_existent_id}/", json=update_data, headers=headers)
    assert response.status_code == 404, f"Expected status code 404, got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie not found"
    assert response_data["detail"] == expected_detail


@pytest.mark.asyncio
async def test_set_movie_reaction_unauthorized(client, create_movies):
    movies = await create_movies(1)
    movie_id = movies[0].id

    response = await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "like"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_set_movie_reaction_movie_not_found(client, create_activated_user_with_token):
    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    invalid_movie_id = 999999
    response = await client.post(f"/movies/{invalid_movie_id}/reaction/", json={"reaction": "like"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found"


@pytest.mark.asyncio
async def test_set_movie_reaction_success(client, db_session, create_movies, create_activated_user_with_token):
    movies = await create_movies(1)
    movie_id = movies[0].id

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"reaction": "like"}

    response = await client.post(f"/movies/{movie_id}/reaction/", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Reaction updated"

    result = await db_session.execute(
        select(MovieReactionModel).where(
            MovieReactionModel.user_id == user.id,
            MovieReactionModel.movie_id == movie_id
        )
    )
    reaction = result.scalar_one()
    assert reaction.reaction == "like"


@pytest.mark.asyncio
async def test_multiple_user_reactions_and_counts(client, db_session, create_movies, create_activated_user_with_token):
    movies = await create_movies(1)
    movie_id = movies[0].id

    users = [await create_activated_user_with_token() for _ in range(3)]
    headers_list = [{"Authorization": f"Bearer {token}"} for _, token in users]

    await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "like"}, headers=headers_list[0])
    await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "dislike"}, headers=headers_list[1])
    await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "like"}, headers=headers_list[2])

    response = await client.get(f"/movies/{movie_id}/")
    data = response.json()
    assert data["likes_count"] == 2
    assert data["dislikes_count"] == 1

    await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "dislike"}, headers=headers_list[0])

    response = await client.get(f"/movies/{movie_id}/")
    data = response.json()
    assert data["likes_count"] == 1
    assert data["dislikes_count"] == 2


@pytest.mark.asyncio
async def test_remove_reaction_success(client, db_session, create_movies, create_activated_user_with_token):
    movies = await create_movies(1)
    movie_id = movies[0].id

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": "like"}, headers=headers)

    response = await client.post(f"/movies/{movie_id}/reaction/", json={"reaction": None}, headers=headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Reaction removed"

    result = await db_session.execute(
        select(MovieReactionModel).where(
            MovieReactionModel.user_id == user.id,
            MovieReactionModel.movie_id == movie_id
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_rate_movie_unauthorized(client, create_movies):
    movies = await create_movies(1)
    movie_id = movies[0].id

    response = await client.post(f"/movies/{movie_id}/rate/", json={"rating": 4})
    assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_movie_not_found(client, create_activated_user_with_token):
        user, token = await create_activated_user_with_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(f"/movies/999999/rate/", json={"rating": 4}, headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


@pytest.mark.asyncio
async def test_rate_movie_success(client, db_session, create_movies, create_activated_user_with_token):
    movies = await create_movies(1)
    movie_id = movies[0].id

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/movies/{movie_id}/rate/", json={"rating": 4}, headers=headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Rating updated"

    result = await db_session.execute(
        select(MovieRatingModel).where(
            MovieRatingModel.user_id == user.id,
            MovieRatingModel.movie_id == movie_id
        )
    )
    rating = result.scalar_one()
    assert rating.rating == 4


@pytest.mark.asyncio
async def test_multiple_users_rating_and_average(client, create_movies, create_activated_user_with_token):
    movies = await create_movies(1)
    movie_id = movies[0].id

    users = [await create_activated_user_with_token() for _ in range(3)]
    headers_list = [{"Authorization": f"Bearer {token}"} for _, token in users]
    ratings = [3, 4, 5]

    for i in range(3):
        response = await client.post(f"/movies/{movie_id}/rate/", json={"rating": ratings[i]}, headers=headers_list[i])
        assert response.status_code == 200

    response = await client.get(f"/movies/{movie_id}/")
    data = response.json()

    assert data["average_rating"] == 4.0


@pytest.mark.asyncio
async def test_create_comment_unauthorized(client, create_movies):
    movie = (await create_movies(1))[0]
    response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Test comment"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_comment_movie_not_found(client, create_activated_user_with_token):
    _, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/movies/999999/comments/",
        json={"content": "Test comment"},
        headers=headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Movies not found"


@pytest.mark.asyncio
async def test_create_comment_success(client, create_movies, create_activated_user_with_token):
    movie = (await create_movies(1))[0]
    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Awesome movie!"},
        headers=headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Awesome movie!"
    assert data["movie_id"] == movie.id
    assert data["user_id"] == user.id
    assert data["user_email"] == user.email


@pytest.mark.asyncio
async def test_get_comments_with_replies_with_reactions(
    client,
    create_activated_user_with_token,
    create_movies,
):
    movies = await create_movies(1)
    movie = movies[0]

    user, token = await create_activated_user_with_token()
    headers = {"Authorization": f"Bearer {token}"}

    root_response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Root comment"},
        headers=headers
    )
    assert root_response.status_code == 201
    root_comment = root_response.json()
    root_id = root_comment["id"]

    reply_response = await client.post(
        f"/comments/{root_id}/reply/",
        json={"content": "This is a reply"},
        headers=headers
    )
    assert reply_response.status_code == 201
    reply = reply_response.json()
    reply_id = reply["id"]

    root_like_response = await client.post(
        f"/comments/{root_id}/reaction/",
        json={"reaction": "like"},
        headers=headers
    )
    assert root_like_response.status_code == 200

    reply_dislike_response = await client.post(
        f"/comments/{reply_id}/reaction/",
        json={"reaction": "dislike"},
        headers=headers
    )
    assert reply_dislike_response.status_code == 200

    get_response = await client.get(f"/movies/{movie.id}/comments/")
    assert get_response.status_code == 200

    comments = get_response.json()
    assert isinstance(comments, list)
    assert len(comments) == 1

    root = comments[0]
    assert root["id"] == root_id
    assert root["content"] == "Root comment"
    assert root["user_email"] == user.email
    assert root["likes_count"] == 1
    assert root["dislikes_count"] == 0

    replies = root["replies"]
    assert len(replies) == 1
    reply = replies[0]
    assert reply["id"] == reply_id
    assert reply["content"] == "This is a reply"
    assert reply["parent_id"] == root_id
    assert reply["user_email"] == user.email
    assert reply["likes_count"] == 0
    assert reply["dislikes_count"] == 1
