certification_example = {
    "id": 1,
    "name": "PG-13"
}

genre_example = {
    "id": 1,
    "name": "Action",
    "movie_count": 150
}

star_example = {
    "id": 1,
    "name": "Leonardo DiCaprio"
}

director_example = {
    "id": 1,
    "name": "Christopher Nolan"
}

movie_create_example = {
    "name": "Inception",
    "year": 2010,
    "time": 148,
    "imdb": 8.8,
    "votes": 2300000,
    "description": "A thief who steals corporate secrets...",
    "price": "14.99",
    "meta_score": 74.0,
    "gross": 836.8,
    "certification": "PG-13",
    "genres": ["Action", "Sci-Fi"],
    "directors": ["Christopher Nolan"],
    "stars": ["Leonardo DiCaprio", "Joseph Gordon-Levitt"]
}

movie_list_item_example = {
    "id": 1,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Inception",
    "year": 2010,
    "time": 148,
    "imdb": 8.8,
    "votes": 2300000,
    "description": "A thief who steals corporate secrets...",
    "price": "14.99",
    "certification": certification_example,
    "genres": [genre_example],
    "directors": [director_example],
    "stars": [star_example]
}

movie_detail_example = {
    **movie_list_item_example,
    "meta_score": 74.0,
    "gross": 836.8
}

movie_list_response_example = {
    "movies": [movie_list_item_example],
    "total_items": 100,
    "total_pages": 10,
    "current_page": 1
}

genre_list_example = {
    "genres": [
        {"id": 1, "name": "Action", "movie_count": 150},
        {"id": 2, "name": "Drama", "movie_count": 75}
    ],
    "total": 2
}
