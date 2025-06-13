from datetime import datetime, timezone

from email_validator import validate_email, EmailNotValidError
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from validation.users import validate_url
import pytest
import httpx
from bs4 import BeautifulSoup

from database import (
    ActivationTokenModel,
    User,
    RefreshTokenModel,
    PasswordResetTokenModel,
)


@pytest.mark.e2e
@pytest.mark.order(8)
@pytest.mark.asyncio
async def test_send_comment_reaction_email(
    e2e_client,
    e2e_db_session,
    settings,
    create_activated_user_with_token,
    create_movies,
):
    user1, token1 = await create_activated_user_with_token()
    user2, token2 = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    comment_data = {"content": "Nice movie!"}
    headers = {"Authorization": f"Bearer {token1}"}

    response = await e2e_client.post(
        f"/movies/{movie.id}/comments/", json=comment_data, headers=headers
    )
    assert response.status_code == 201
    comment_id = response.json()["id"]

    headers = {"Authorization": f"Bearer {token2}"}
    reaction_data = {"reaction": "like"}
    response = await e2e_client.post(
        f"/comments/{comment_id}/reaction/", json=reaction_data, headers=headers
    )

    assert response.status_code == 200

    mailhog_url = f"http://mailhog:{settings.MAILHOG_API_PORT}/api/v2/messages"
    async with httpx.AsyncClient() as client:
        mailhog_response = await client.get(mailhog_url)

    assert mailhog_response.status_code == 200
    messages = mailhog_response.json()["items"]
    assert any(
        "New Reaction to Your Comment"
        in m["Content"]["Headers"].get("Subject", [""])[0]
        for m in messages
    )


@pytest.mark.e2e
@pytest.mark.order(9)
@pytest.mark.asyncio
async def test_send_comment_reply_email(
    e2e_client,
    e2e_db_session,
    settings,
    create_activated_user_with_token,
    create_movies,
):
    user1, token1 = await create_activated_user_with_token()
    user2, token2 = await create_activated_user_with_token()
    movies = await create_movies(1)
    movie = movies[0]

    comment_data = {"content": "This film is amazing!"}
    headers = {"Authorization": f"Bearer {token1}"}
    response = await e2e_client.post(
        f"/movies/{movie.id}/comments/", json=comment_data, headers=headers
    )

    assert response.status_code == 201
    comment_id = response.json()["id"]

    headers = {"Authorization": f"Bearer {token2}"}
    reply_data = {"content": "I agree with you!", "parent_id": comment_id}
    response = await e2e_client.post(
        f"/comments/{comment_id}/reply/", json=reply_data, headers=headers
    )
    assert response.status_code == 201

    mailhog_url = f"http://mailhog:{settings.MAILHOG_API_PORT}/api/v2/messages"
    async with httpx.AsyncClient() as client:
        mailhog_response = await client.get(mailhog_url)

    assert mailhog_response.status_code == 200
    messages = mailhog_response.json()["items"]
    assert any(
        "New Reply to Your Comment" in m["Content"]["Headers"].get("Subject", [""])[0]
        for m in messages
    )
