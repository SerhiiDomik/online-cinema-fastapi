import pytest
from database.models.movies import ReactionEnum


@pytest.mark.asyncio
async def test_reply_to_comment_success(
    client, create_activated_user_with_token, create_movies
):
    user, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Original comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    comment_id = response.json()["id"]

    reply_response = await client.post(
        f"/comments/{comment_id}/reply/",
        json={"content": "Reply to comment"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert reply_response.status_code == 201
    data = reply_response.json()
    assert data["content"] == "Reply to comment"
    assert data["parent_id"] == comment_id
    assert data["user_id"] == user.id


@pytest.mark.asyncio
async def test_reply_to_nonexistent_comment(client, create_activated_user_with_token):
    _, token = await create_activated_user_with_token()
    non_existent_id = 99999

    response = await client.post(
        f"/comments/{non_existent_id}/reply/",
        json={"content": "This won't work"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent comment not found"


@pytest.mark.asyncio
async def test_reply_to_comment_unauthorized(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Original comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = response.json()["id"]

    response = await client.post(
        f"/comments/{comment_id}/reply/",
        json={"content": "Unauthorized reply"},
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_reply_to_comment_invalid_data(
    client, create_activated_user_with_token, create_movies
):
    _, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Original comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = response.json()["id"]

    response = await client.post(
        f"/comments/{comment_id}/reply/",
        json={"content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_comment_reaction_success(
    client, create_activated_user_with_token, create_movies
):
    user, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    comment_response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Test comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = comment_response.json()["id"]

    reaction_response = await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reaction_response.status_code == 200
    assert reaction_response.json()["detail"] == "Reaction updated"


@pytest.mark.asyncio
async def test_reaction_reply(client, create_activated_user_with_token, create_movies):
    user, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    parent_comment = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Parent comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    parent_id = parent_comment.json()["id"]

    reply_response = await client.post(
        f"/comments/{parent_id}/reply/",
        json={"content": "Reply comment"},
        headers={"Authorization": f"Bearer {token}"},
    )

    reply_id = reply_response.json()["id"]

    reaction_response = await client.post(
        f"/comments/{reply_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert reaction_response.status_code == 200
    assert reaction_response.json()["detail"] == "Reaction updated"

    comment_response = await client.get(
        f"/comments/{reply_id}/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert comment_response.status_code == 200
    assert comment_response.json()["likes_count"] == 1
    assert comment_response.json()["dislikes_count"] == 0


@pytest.mark.asyncio
async def test_update_reaction_with_counts(
    client, create_activated_user_with_token, create_movies
):
    user, token = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    comment_response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Test comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = comment_response.json()["id"]

    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token}"},
    )

    comment_after_like = await client.get(
        f"/comments/{comment_id}/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert comment_after_like.json()["likes_count"] == 1
    assert comment_after_like.json()["dislikes_count"] == 0

    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.DISLIKE.value},
        headers={"Authorization": f"Bearer {token}"},
    )

    comment_after_dislike = await client.get(
        f"/comments/{comment_id}/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert comment_after_dislike.json()["likes_count"] == 0
    assert comment_after_dislike.json()["dislikes_count"] == 1

    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": None},
        headers={"Authorization": f"Bearer {token}"},
    )

    comment_after_remove = await client.get(
        f"/comments/{comment_id}/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert comment_after_remove.json()["likes_count"] == 0
    assert comment_after_remove.json()["dislikes_count"] == 0


@pytest.mark.asyncio
async def test_multiple_users_reactions(
    client, create_activated_user_with_token, create_movies
):
    user1, token1 = await create_activated_user_with_token()
    user2, token2 = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    comment_response = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Test comment"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    comment_id = comment_response.json()["id"]

    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token1}"},
    )
    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token2}"},
    )

    comment_response = await client.get(
        f"/comments/{comment_id}/",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert comment_response.json()["likes_count"] == 2
    assert comment_response.json()["dislikes_count"] == 0

    await client.post(
        f"/comments/{comment_id}/reaction/",
        json={"reaction": ReactionEnum.DISLIKE.value},
        headers={"Authorization": f"Bearer {token1}"},
    )

    comment_response = await client.get(
        f"/comments/{comment_id}/",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert comment_response.json()["likes_count"] == 1
    assert comment_response.json()["dislikes_count"] == 1


@pytest.mark.asyncio
async def test_reaction_to_nonexistent_comment(
    client, create_activated_user_with_token
):
    _, token = await create_activated_user_with_token()

    response = await client.post(
        "/comments/999999/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Comment not found"


@pytest.mark.asyncio
async def test_reaction_unauthorized(client):
    response = await client.post(
        "/comments/1/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_get_comment_with_replies_full(
    client, create_activated_user_with_token, create_movies
):
    user1, token1 = await create_activated_user_with_token()
    user2, token2 = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    root1 = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Root comment 1"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    root1_id = root1.json()["id"]
    root2 = await client.post(
        f"/movies/{movie.id}/comments/",
        json={"content": "Root comment 2"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    root2_id = root2.json()["id"]

    reply1 = await client.post(
        f"/comments/{root1_id}/reply/",
        json={"content": "Reply to root1"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    reply1_id = reply1.json()["id"]
    reply2 = await client.post(
        f"/comments/{root1_id}/reply/",
        json={"content": "Another reply to root1"},
        headers={"Authorization": f"Bearer {token2}"},
    )

    nested_reply1 = await client.post(
        f"/comments/{reply1_id}/reply/",
        json={"content": "Nested reply"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    nested_reply1_id = nested_reply1.json()["id"]

    await client.post(
        f"/comments/{reply1_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token1}"},
    )
    await client.post(
        f"/comments/{reply1_id}/reaction/",
        json={"reaction": ReactionEnum.LIKE.value},
        headers={"Authorization": f"Bearer {token2}"},
    )

    await client.post(
        f"/comments/{nested_reply1_id}/reaction/",
        json={"reaction": ReactionEnum.DISLIKE.value},
        headers={"Authorization": f"Bearer {token2}"},
    )

    response = await client.get(f"/comments/{root1_id}/")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == root1_id
    assert len(data["replies"]) == 2

    reply1_data = next(r for r in data["replies"] if r["id"] == reply1_id)
    assert reply1_data["likes_count"] == 2
    assert reply1_data["dislikes_count"] == 0
    assert len(reply1_data["replies"]) == 1

    nested_reply1_data = reply1_data["replies"][0]
    assert nested_reply1_data["id"] == nested_reply1_id
    assert nested_reply1_data["likes_count"] == 0
    assert nested_reply1_data["dislikes_count"] == 1

    response = await client.get(f"/comments/{reply1_id}/")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == reply1_id
    assert data["parent_id"] == root1_id
    assert len(data["replies"]) == 1
    assert data["likes_count"] == 2
    assert data["dislikes_count"] == 0

    response = await client.get(f"/comments/{root2_id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == root2_id
    assert len(data["replies"]) == 0
