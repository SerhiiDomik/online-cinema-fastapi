from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select, delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from database import (
    User,
    ActivationTokenModel,
    PasswordResetTokenModel,
    UserGroup,
    UserGroupEnum,
    RefreshTokenModel,
)


@pytest.mark.asyncio
async def test_register_user_success(client, db_session, seed_user_groups):
    payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}

    response = await client.post("/users/register/", json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload["email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."

    stmt_user = select(User).where(User.email == payload["email"])
    result = await db_session.execute(stmt_user)
    created_user = result.scalars().first()
    assert created_user is not None, "User was not created in the database."
    assert (
        created_user.email == payload["email"]
    ), "Created user's email does not match."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id
    )
    result = await db_session.execute(stmt_token)
    activation_token = result.scalars().first()
    assert (
        activation_token is not None
    ), "Activation token was not created in the database."
    assert (
        activation_token.user_id == created_user.id
    ), "Activation token's user_id does not match."
    assert activation_token.token is not None, "Activation token has no token value."

    expires_at = activation_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc
    ), "Activation token is already expired."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_password, expected_error",
    [
        ("short", "Password must contain at least 8 characters."),
        ("NoDigitHere!", "Password must contain at least one digit."),
        ("nodigitnorupper@", "Password must contain at least one uppercase letter."),
        ("NOLOWERCASE1@", "Password must contain at least one lower letter."),
        (
            "NoSpecial123",
            "Password must contain at least one special character: @, $, !, %, *, ?, #, &.",
        ),
    ],
)
async def test_register_user_password_validation(
    client, seed_user_groups, invalid_password, expected_error
):
    payload = {"email": "testuser@example.com", "password": invalid_password}

    response = await client.post("/users/register/", json=payload)
    assert response.status_code == 422, "Expected status code 422 for invalid input."

    response_data = response.json()
    assert expected_error in str(
        response_data
    ), f"Expected error message: {expected_error}"


@pytest.mark.asyncio
async def test_register_user_conflict(client, db_session, seed_user_groups):
    payload = {"email": "conflictuser@example.com", "password": "StrongPassword123!"}

    response_first = await client.post("/users/register/", json=payload)
    assert (
        response_first.status_code == 201
    ), "Expected status code 201 for the first registration."

    stmt = select(User).where(User.email == payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert (
        created_user is not None
    ), "User should be created after the first registration."

    response_second = await client.post("/users/register/", json=payload)
    assert (
        response_second.status_code == 409
    ), "Expected status code 409 for a duplicate registration."

    response_data = response_second.json()
    expected_message = f"A user with this email {payload['email']} already exists."
    assert (
        response_data["detail"] == expected_message
    ), f"Expected error message: {expected_message}"


@pytest.mark.asyncio
async def test_register_user_internal_server_error(client, seed_user_groups):
    payload = {"email": "erroruser@example.com", "password": "StrongPassword123!"}

    with patch("routes.users.AsyncSession.commit", side_effect=SQLAlchemyError):
        response = await client.post("/users/register/", json=payload)

        assert (
            response.status_code == 500
        ), "Expected status code 500 for internal server error."

        response_data = response.json()
        expected_message = "An error occurred during user creation."
        assert (
            response_data["detail"] == expected_message
        ), f"Expected error message: {expected_message}"


@pytest.mark.asyncio
async def test_activate_account_success(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }

    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = (
        select(User)
        .options(joinedload(User.activation_token))
        .where(User.email == registration_payload["email"])
    )
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User was not created in the database."
    assert not user.is_active, "Newly registered user should not be active."

    assert (
        user.activation_token is not None and user.activation_token.token is not None
    ), "Activation token was not created in the database."

    activation_payload = {
        "email": registration_payload["email"],
        "token": user.activation_token.token,
    }

    activation_response = await client.post("/users/activate/", json=activation_payload)
    assert (
        activation_response.status_code == 200
    ), "Expected status code 200 for successful activation."
    assert (
        activation_response.json()["message"] == "User account activated successfully."
    )

    stmt = (
        select(User)
        .options(joinedload(User.activation_token))
        .where(User.email == registration_payload["email"])
    )
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    await db_session.refresh(user)
    assert user.is_active, "User should be active after successful activation."

    stmt = select(ActivationTokenModel).where(ActivationTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    token = result.scalars().first()
    assert (
        token is None
    ), "Activation token should be deleted after successful activation."


@pytest.mark.asyncio
async def test_activate_user_with_expired_token(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    activation_token.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
    await db_session.commit()

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = await client.post("/users/activate/", json=activation_payload)

    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for expired token."
    assert (
        activation_response.json()["detail"] == "Invalid or expired activation token."
    ), "Expected error message for expired token."


@pytest.mark.asyncio
async def test_activate_user_with_deleted_token(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    token_value = activation_token.token

    await db_session.execute(
        delete(ActivationTokenModel).where(
            ActivationTokenModel.id == activation_token.id
        )
    )
    await db_session.commit()

    activation_payload = {"email": registration_payload["email"], "token": token_value}
    activation_response = await client.post("/users/activate/", json=activation_payload)
    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for deleted token."
    assert (
        activation_response.json()["detail"] == "Invalid or expired activation token."
    ), "Expected error message for deleted token."


@pytest.mark.asyncio
async def test_activate_already_active_user(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }

    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = await client.post("/users/activate/", json=activation_payload)
    assert (
        activation_response.status_code == 400
    ), "Expected status code 400 for already active user."
    assert (
        activation_response.json()["detail"] == "User account is already active."
    ), "Expected error message for already active user."


@pytest.mark.asyncio
async def test_resend_activation_inactive_user(client, db_session, seed_user_groups):
    user_email = "inactive@example.com"
    register_payload = {"email": user_email, "password": "StrongPassword123!"}
    register_response = await client.post("/users/register/", json=register_payload)
    assert register_response.status_code == 201

    stmt_user = select(User).where(User.email == user_email)
    result_user = await db_session.execute(stmt_user)
    user = result_user.scalars().first()
    assert user is not None
    assert not user.is_active

    stmt_token1 = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id
    )
    result_token1 = await db_session.execute(stmt_token1)
    token1 = result_token1.scalars().first()
    assert token1 is not None

    token1.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    response = await client.post(f"/users/resend-activation/?email={user_email}")
    assert response.status_code == 200
    data = response.json()
    assert data.get("message") == "New activation token has been sent to your email"

    stmt_token2 = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id
    )
    result_token2 = await db_session.execute(stmt_token2)
    tokens = result_token2.scalars().all()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_resend_activation_already_active_user(
    client, db_session, seed_user_groups
):
    user_email = "active@example.com"
    register_payload = {"email": user_email, "password": "StrongPassword123!"}
    register_response = await client.post("/users/register/", json=register_payload)
    assert register_response.status_code == 201

    stmt_user = select(User).where(User.email == user_email)
    result_user = await db_session.execute(stmt_user)
    user = result_user.scalars().first()
    assert user is not None
    user.is_active = True
    await db_session.commit()

    response = await client.post(f"/users/resend-activation/?email={user_email}")
    assert response.status_code == 400
    data = response.json()
    assert data.get("detail") == "User account is already active"


@pytest.mark.asyncio
async def test_resend_activation_nonexistent_email(
    client, db_session, seed_user_groups
):
    stmt_all_tokens_before = select(ActivationTokenModel)
    result_all_before = await db_session.execute(stmt_all_tokens_before)
    tokens_before = result_all_before.scalars().all()
    count_before = len(tokens_before)

    random_email = "noone@doesnotexist.test"
    response = await client.post(f"/users/resend-activation/?email={random_email}")
    assert response.status_code == 422

    stmt_all_after = select(ActivationTokenModel)
    result_all_after = await db_session.execute(stmt_all_after)
    tokens_after = result_all_after.scalars().all()
    count_after = len(tokens_after)

    assert count_after == count_before


@pytest.mark.asyncio
async def test_request_password_reset_token_success(
    client, db_session, seed_user_groups
):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_payload = {"email": registration_payload["email"]}
    reset_response = await client.post(
        "/users/password-reset/request/", json=reset_payload
    )
    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for successful token request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected success message for password reset token request."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    reset_token = result_token.scalars().first()
    assert (
        reset_token is not None
    ), "Password reset token should be created for the user."

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc
    ), "Password reset token should have a future expiration date."


@pytest.mark.asyncio
async def test_request_password_reset_token_nonexistent_user(client, db_session):
    reset_payload = {"email": "nonexistent@example.com"}

    reset_response = await client.post(
        "/users/password-reset/request/", json=reset_payload
    )
    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for non-existent user request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected generic success message for non-existent user request."

    stmt = select(func.count(PasswordResetTokenModel.id))
    result = await db_session.execute(stmt)
    reset_token_count = result.scalar_one()
    assert (
        reset_token_count == 0
    ), "No password reset token should be created for non-existent user."


@pytest.mark.asyncio
async def test_request_password_reset_token_for_inactive_user(
    client, db_session, seed_user_groups
):
    registration_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert created_user is not None, "User should be created in the database."
    assert not created_user.is_active, "User should not be active after registration."

    reset_payload = {"email": registration_payload["email"]}
    reset_response = await client.post(
        "/users/password-reset/request/", json=reset_payload
    )
    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for inactive user password reset request."
    assert (
        reset_response.json()["message"]
        == "If you are registered, you will receive an email with instructions."
    ), "Expected generic success message for inactive user password reset request."

    stmt_tokens = select(func.count(PasswordResetTokenModel.id))
    result_tokens = await db_session.execute(stmt_tokens)
    reset_token_count = result_tokens.scalar_one()
    assert (
        reset_token_count == 0
    ), "No password reset token should be created for an inactive user."


@pytest.mark.asyncio
async def test_reset_password_success(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "OldPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert (
        registration_response.status_code == 201
    ), "Expected status code 201 for successful registration."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert created_user is not None, "User should be created in the database."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id
    )
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert (
        activation_token is not None
    ), "Activation token should be created in the database."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token,
    }
    activation_response = await client.post("/users/activate/", json=activation_payload)
    assert (
        activation_response.status_code == 200
    ), "Expected status code 200 for successful activation."

    await db_session.refresh(created_user)
    assert created_user.is_active, "User should be active after successful activation."

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/users/password-reset/request/", json=reset_request_payload
    )
    assert (
        reset_request_response.status_code == 200
    ), "Expected status code 200 for password reset token request."

    stmt_reset = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == created_user.id
    )
    result_reset = await db_session.execute(stmt_reset)
    reset_token_record = result_reset.scalars().first()
    assert (
        reset_token_record is not None
    ), "Password reset token should be created in the database."

    new_password = "NewSecurePassword123!"
    reset_payload = {
        "email": registration_payload["email"],
        "token": reset_token_record.token,
        "password": new_password,
    }
    reset_response = await client.post(
        "/users/password-reset/complete/", json=reset_payload
    )
    assert (
        reset_response.status_code == 200
    ), "Expected status code 200 for successful password reset."
    assert (
        reset_response.json()["message"] == "Password reset successfully."
    ), "Unexpected response message for password reset."

    await db_session.refresh(created_user)
    assert created_user.verify_password(
        new_password
    ), "Password should be updated successfully in the database."


@pytest.mark.asyncio
async def test_reset_password_invalid_email(client, db_session):
    reset_payload = {
        "email": "nonexistent@example.com",
        "token": "random_token",
        "password": "NewSecurePassword123!",
    }

    response = await client.post("/users/password-reset/complete/", json=reset_payload)

    assert response.status_code == 400, "Expected status code 400 for invalid email."
    assert (
        response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    response = await client.post("/users/register/", json=registration_payload)
    assert response.status_code == 201, "User registration failed."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    response = await client.post(
        "/users/password-reset/request/", json=reset_request_payload
    )
    assert response.status_code == 200, "Password reset request failed."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": "incorrect_token",
        "password": "NewSecurePassword123!",
    }
    response = await client.post(
        "/users/password-reset/complete/", json=reset_complete_payload
    )
    assert response.status_code == 400, "Expected status code 400 for invalid token."
    assert (
        response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is None, "Invalid token was not removed."


@pytest.mark.asyncio
async def test_reset_password_expired_token(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert registration_response.status_code == 201, "User registration failed."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/users/password-reset/request/", json=reset_request_payload
    )
    assert reset_request_response.status_code == 200, "Password reset request failed."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is not None, "Password reset token not created."

    token_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!",
    }
    reset_response = await client.post(
        "/users/password-reset/complete/", json=reset_complete_payload
    )
    assert (
        reset_response.status_code == 400
    ), "Expected status code 400 for expired token."
    assert (
        reset_response.json()["detail"] == "Invalid email or token."
    ), "Unexpected error message."

    stmt_token_check = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    result_token_check = await db_session.execute(stmt_token_check)
    expired_token = result_token_check.scalars().first()
    assert expired_token is None, "Expired token was not removed."


@pytest.mark.asyncio
async def test_reset_password_sqlalchemy_error(client, db_session, seed_user_groups):
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!",
    }
    registration_response = await client.post(
        "/users/register/", json=registration_payload
    )
    assert registration_response.status_code == 201, "User registration failed."

    stmt = select(User).where(User.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/users/password-reset/request/", json=reset_request_payload
    )
    assert reset_request_response.status_code == 200, "Password reset request failed."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is not None, "Password reset token not created."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!",
    }

    with patch("routes.users.AsyncSession.commit", side_effect=SQLAlchemyError):
        reset_response = await client.post(
            "/users/password-reset/complete/", json=reset_complete_payload
        )

    assert (
        reset_response.status_code == 500
    ), "Expected status code 500 for SQLAlchemyError."
    assert (
        reset_response.json()["detail"]
        == "An error occurred while resetting the password."
    ), "Unexpected error message for SQLAlchemyError."


@pytest.mark.asyncio
async def test_login_user_success(client, db_session, jwt_manager, seed_user_groups):
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}

    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    response = await client.post("/users/login/", json=login_payload)
    assert response.status_code == 201, "Expected status code 201 for successful login."
    response_data = response.json()
    assert "access_token" in response_data, "Access token is missing in the response."
    assert "refresh_token" in response_data, "Refresh token is missing in the response."
    assert response_data["access_token"], "Access token is empty."
    assert response_data["refresh_token"], "Refresh token is empty."

    access_token_data = jwt_manager.decode_access_token(response_data["access_token"])
    assert access_token_data["sub"] == str(
        user.id
    ), "Access token does not contain correct user ID."

    refresh_token_data = jwt_manager.decode_refresh_token(
        response_data["refresh_token"]
    )
    assert refresh_token_data["sub"] == str(
        user.id
    ), "Refresh token does not contain correct user ID."

    stmt_refresh = select(RefreshTokenModel).where(RefreshTokenModel.user_id == user.id)
    result_refresh = await db_session.execute(stmt_refresh)
    refresh_token_record = result_refresh.scalars().first()
    assert (
        refresh_token_record is not None
    ), "Refresh token was not stored in the database."
    assert (
        refresh_token_record.token == response_data["refresh_token"]
    ), "Stored refresh token does not match."

    expires_at = refresh_token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(timezone.utc), "Refresh token is already expired."


@pytest.mark.asyncio
async def test_login_user_invalid_cases(client, db_session, seed_user_groups):
    login_payload = {"email": "nonexistent@example.com", "password": "SomePassword123!"}
    response = await client.post("/users/login/", json=login_payload)
    assert (
        response.status_code == 401
    ), "Expected status code 401 for non-existent user."
    assert (
        response.json()["detail"] == "Invalid email or password."
    ), "Unexpected error message for non-existent user."

    user_payload = {"email": "testuser@example.com", "password": "CorrectPassword123!"}
    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload_incorrect_password = {
        "email": user_payload["email"],
        "password": "WrongPassword123!",
    }
    response = await client.post("/users/login/", json=login_payload_incorrect_password)
    assert (
        response.status_code == 401
    ), "Expected status code 401 for incorrect password."
    assert (
        response.json()["detail"] == "Invalid email or password."
    ), "Unexpected error message for incorrect password."


@pytest.mark.asyncio
async def test_login_user_inactive_account(client, db_session, seed_user_groups):
    user_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!",
    }

    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "User group not found."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = False
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    response = await client.post("/users/login/", json=login_payload)

    assert response.status_code == 403, "Expected status code 403 for inactive user."
    assert (
        response.json()["detail"] == "User account is not activated."
    ), "Unexpected error message for inactive user."


@pytest.mark.asyncio
async def test_login_user_commit_error(client, db_session, seed_user_groups):
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }

    with patch("routes.users.AsyncSession.commit", side_effect=SQLAlchemyError):
        response = await client.post("/users/login/", json=login_payload)

    assert (
        response.status_code == 500
    ), "Expected status code 500 for database commit error."
    assert (
        response.json()["detail"] == "An error occurred while processing the request."
    ), "Unexpected error message for database commit error."


async def test_logout_user_success(client, db_session, jwt_manager, seed_user_groups):
    stmt_group = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result_group = await db_session.execute(stmt_group)
    user_group = result_group.scalars().first()
    if not user_group:
        user_group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(user_group)
        await db_session.flush()

    user = User.create(
        email="logoutuser@example.com",
        raw_password="StrongPassword123!",
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": "logoutuser@example.com",
        "password": "StrongPassword123!",
    }
    login_response = await client.post("/users/login/", json=login_payload)
    assert login_response.status_code == 201, "Expected 201 for successful login"
    tokens = login_response.json()
    refresh_token = tokens["refresh_token"]

    stmt_refresh_before = select(RefreshTokenModel).where(
        RefreshTokenModel.token == refresh_token
    )
    result_refresh_before = await db_session.execute(stmt_refresh_before)
    refresh_record_before = result_refresh_before.scalars().first()
    assert (
        refresh_record_before is not None
    ), "Refresh token record should exist before logout"

    logout_payload = {"refresh_token": refresh_token}
    logout_response = await client.post("/users/logout/", json=logout_payload)
    assert logout_response.status_code == 200, "Expected 200 for successful logout"
    response_data = logout_response.json()
    assert (
        response_data["message"] == "Successfully logged out."
    ), "Unexpected logout message"

    stmt_refresh_after = select(RefreshTokenModel).where(
        RefreshTokenModel.token == refresh_token
    )
    result_refresh_after = await db_session.execute(stmt_refresh_after)
    refresh_record_after = result_refresh_after.scalars().first()
    assert (
        refresh_record_after is None
    ), "Refresh token record should be deleted after logout"


@pytest.mark.asyncio
async def test_logout_user_invalid_token(client, db_session, seed_user_groups):
    invalid_token = "some.random.invalid.token"

    logout_payload = {"refresh_token": invalid_token}
    logout_response = await client.post("/users/logout/", json=logout_payload)
    assert logout_response.status_code == 400, "Expected 400 for invalid refresh token"
    response_data = logout_response.json()
    assert (
        response_data["detail"] == "Invalid refresh token."
    ), "Expected 'Invalid refresh token.' detail"


@pytest.mark.asyncio
async def test_refresh_access_token_success(
    client, db_session, jwt_manager, seed_user_groups
):
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}
    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }
    login_response = await client.post("/users/login/", json=login_payload)
    assert (
        login_response.status_code == 201
    ), "Expected status code 201 for successful login."
    login_data = login_response.json()
    refresh_token = login_data["refresh_token"]

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post("/users/refresh/", json=refresh_payload)
    assert (
        refresh_response.status_code == 200
    ), "Expected status code 200 for successful token refresh."
    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data, "Access token is missing in the response."
    assert refresh_data["access_token"], "Access token is empty."

    access_token_data = jwt_manager.decode_access_token(refresh_data["access_token"])
    assert access_token_data["sub"] == str(
        user.id
    ), "Access token does not contain correct user ID."


@pytest.mark.asyncio
async def test_refresh_access_token_expired_token(client, jwt_manager):
    expired_token = jwt_manager.create_refresh_token(
        {"sub": 1}, expires_delta=timedelta(days=-1)
    )

    refresh_payload = {"refresh_token": expired_token}
    refresh_response = await client.post("/users/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 400
    ), "Expected status code 400 for expired token."
    assert (
        refresh_response.json()["detail"] == "Token has expired."
    ), "Unexpected error message."


@pytest.mark.asyncio
async def test_refresh_access_token_token_not_found(client, jwt_manager):
    refresh_token = jwt_manager.create_refresh_token({"sub": "1"})
    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post("/users/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 401
    ), "Expected status code 401 for token not found."
    assert (
        refresh_response.json()["detail"] == "Refresh token not found."
    ), "Unexpected error message."


@pytest.mark.asyncio
async def test_refresh_access_token_user_not_found(
    client, db_session, jwt_manager, seed_user_groups
):
    user_payload = {"email": "testuser@example.com", "password": "StrongPassword123!"}

    stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = User.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    invalid_user_id = 9999
    refresh_token = jwt_manager.create_refresh_token({"sub": str(invalid_user_id)})

    refresh_token_record = RefreshTokenModel.create(
        user_id=invalid_user_id, days_valid=7, token=refresh_token
    )
    db_session.add(refresh_token_record)
    await db_session.commit()

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post("/users/refresh/", json=refresh_payload)

    assert (
        refresh_response.status_code == 404
    ), "Expected status code 404 for non-existent user."
    assert (
        refresh_response.json()["detail"] == "User not found."
    ), "Unexpected error message."
