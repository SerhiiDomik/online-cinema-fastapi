import os
import uuid
from decimal import Decimal
from typing import List

import httpx
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    get_settings,
    get_users_email_notificator,
    get_s3_storage_client
)
from database import (
    reset_database,
    get_db_contextmanager,
    UserGroupEnum,
    UserGroup,
    User, GenreModel,
)
from database.models import MovieModel, CertificationModel, StarModel, DirectorModel
from main import app
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from storages import S3StorageClient
from tests.doubles.fakes.storage import FakeS3Storage
from tests.doubles.stubs.emails import StubEmailSender

os.environ["ENVIRONMENT"] = "testing"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests"
    )
    config.addinivalue_line(
        "markers", "order: Specify the order of test execution"
    )
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db(request):
    """
    Reset the SQLite database before each test function, except for tests marked with 'e2e'.

    By default, this fixture ensures that the database is cleared and recreated before every
    test function to maintain test isolation. However, if the test is marked with 'e2e',
    the database reset is skipped to allow preserving state between end-to-end tests.
    """
    if "e2e" in request.keywords:
        yield
    else:
        await reset_database()
        yield


@pytest_asyncio.fixture(scope="session")
async def reset_db_once_for_e2e(request):
    """
    Reset the database once for end-to-end tests.

    This fixture is intended to be used for end-to-end tests at the session scope,
    ensuring the database is reset before running E2E tests.
    """
    await reset_database()


@pytest_asyncio.fixture(scope="session")
async def settings():
    """
    Provide application settings.

    This fixture returns the application settings by calling get_settings().
    """
    return get_settings()


@pytest_asyncio.fixture(scope="function")
async def email_sender_stub():
    """
    Provide a stub implementation of the email sender.

    This fixture returns an instance of StubEmailSender for testing purposes.
    """
    return StubEmailSender()


@pytest_asyncio.fixture(scope="function")
async def s3_storage_fake():
    """
    Provide a fake S3 storage client.

    This fixture returns an instance of FakeS3Storage for testing purposes.
    """
    return FakeS3Storage()


@pytest_asyncio.fixture(scope="session")
async def s3_client(settings):
    """
    Provide an S3 storage client.

    This fixture returns an instance of S3StorageClient configured with the application settings.
    """
    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )


@pytest_asyncio.fixture(scope="function")
async def client(email_sender_stub, s3_storage_fake):
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender and S3 storage with test doubles.
    """
    app.dependency_overrides[get_users_email_notificator] = lambda: email_sender_stub
    app.dependency_overrides[get_s3_storage_client] = lambda: s3_storage_fake

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def e2e_client():
    """
    Provide an asynchronous HTTP client for end-to-end tests.

    This client is available at the session scope.
    """

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide an async database session for database interactions.

    This fixture yields an async session using `get_db_contextmanager`, ensuring that the session
    is properly closed after each test.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def e2e_db_session(reset_db_once_for_e2e):
    """
    Provide an async database session for end-to-end tests.

    This fixture yields an async session using `get_db_contextmanager` at the session scope,
    ensuring that the same session is used throughout the E2E test suite.
    Note: Using a session-scoped DB session in async tests may lead to shared state between tests,
    so use this fixture with caution if tests run concurrently.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def jwt_manager() -> JWTAuthManagerInterface:
    """
    Asynchronous fixture to create a JWT authentication manager instance.

    This fixture retrieves the application settings via `get_settings()` and uses them to
    instantiate a `JWTAuthManager`. The manager is configured with the secret keys for
    access and refresh tokens, as well as the JWT signing algorithm specified in the settings.

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with the appropriate
        secret keys and algorithm.
    """
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


@pytest_asyncio.fixture(scope="function")
async def seed_user_groups(db_session: AsyncSession):
    """
    Asynchronously seed the UserGroupModel table with default user groups.

    This fixture inserts all user groups defined in UserGroupEnum into the database and commits the transaction.
    It then yields the asynchronous database session for further testing.
    """
    groups = [{"name": group.value} for group in UserGroupEnum]
    await db_session.execute(insert(UserGroup).values(groups))
    await db_session.commit()
    yield db_session


@pytest_asyncio.fixture
async def admin_user_group(e2e_db_session):
    """
        Provide the 'ADMIN' user group.

        If it doesn't exist, create and return it from the E2E database session.
    """
    admin_group = await e2e_db_session.execute(
        select(UserGroup).filter_by(name="ADMIN")
    )
    admin_group = admin_group.scalars().first()
    if not admin_group:
        admin_group = UserGroup(name="ADMIN")
        e2e_db_session.add(admin_group)
        await e2e_db_session.commit()
    return admin_group


@pytest_asyncio.fixture
async def user_group_user(e2e_db_session):
    """
    Provide the 'USER' user group.

    If it doesn't exist, create and return it from the E2E database session.
    """
    user_group = await e2e_db_session.execute(
        select(UserGroup).filter_by(name="USER")
    )
    group = user_group.scalars().first()
    if not group:
        group = UserGroup(name="USER")
        e2e_db_session.add(group)
        await e2e_db_session.commit()
    return group


@pytest_asyncio.fixture
async def create_user(e2e_db_session, admin_user_group):
    """
    Create a non-activated admin user.

    This user is created with a predefined email and password.
    """
    user = User.create(
        email="newtest@email.com",
        raw_password="NewSecurePassword123!",
        group_id=admin_user_group.id
    )
    e2e_db_session.add(user)
    await e2e_db_session.commit()
    await e2e_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def create_activated_user(e2e_db_session, admin_user_group):
    """
    Create and return an activated admin user with a random email.
    """
    email = f"{uuid.uuid4().hex[:4]}@email.com"
    user = User.create(
        email=email,
        raw_password="NewSecurePassword123!",
        group_id=admin_user_group.id
    )
    user.is_active = True
    e2e_db_session.add(user)
    await e2e_db_session.commit()
    await e2e_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
def create_user_with_token(e2e_client: AsyncClient, e2e_db_session):
    def _factory(group_id: int):
        async def _create_user():
            email = f"{uuid.uuid4().hex[:4]}@email.com"
            raw_password = "Password123!"

            user = User.create(
                email=email,
                raw_password=raw_password,
                group_id=group_id,
            )
            user.is_active = True
            e2e_db_session.add(user)
            await e2e_db_session.commit()
            await e2e_db_session.refresh(user)

            response = await e2e_client.post(
                "/users/login/",
                json={"email": email, "password": raw_password}
            )
            access_token = response.json()["access_token"]
            return user, access_token

        return _create_user
    return _factory


@pytest_asyncio.fixture
def create_activated_user_with_token(create_user_with_token, admin_user_group):
    return create_user_with_token(admin_user_group.id)


@pytest_asyncio.fixture
def create_default_user_with_token(create_user_with_token, user_group_user):
    return create_user_with_token(user_group_user.id)


@pytest_asyncio.fixture
def create_movies(db_session):
    """
    Return a function to create a specified number of movies with related genres, certification, directors, and stars.

    Accepts overrides for genres, certification name, directors, and stars.
    """
    async def get_or_create_by_name(model, name_field: str, names: list[str]) -> list:
        """Generic helper to get or create instances by name."""
        instances = []
        for name in names:
            result = await db_session.execute(
                select(model).where(getattr(model, name_field) == name)
            )
            instance = result.scalars().first()
            if not instance:
                instance = model(**{name_field: name})
                db_session.add(instance)
                await db_session.commit()
                await db_session.refresh(instance)
            instances.append(instance)
        return instances

    async def _create_movies(count: int, **overrides) -> List[MovieModel]:
        genres_input = overrides.pop("genres", ["Test genre"])
        genres_input = [genres_input] if isinstance(genres_input, str) else genres_input
        genres = await get_or_create_by_name(GenreModel, "name", genres_input)

        certification_name: str = overrides.pop("certification_name", "Test Certification")
        certification = (await get_or_create_by_name(CertificationModel, "name", [certification_name]))[0]

        directors_input = overrides.pop("directors", ["Test Director"])
        directors_input = [directors_input] if isinstance(directors_input, str) else directors_input
        directors = await get_or_create_by_name(DirectorModel, "name", directors_input)

        stars_input = overrides.pop("stars", ["Test Star"])
        stars_input = [stars_input] if isinstance(stars_input, str) else stars_input
        stars = await get_or_create_by_name(StarModel, "name", stars_input)

        movies = []
        for i in range(count):
            movie = MovieModel(
                uuid=str(uuid.uuid4()),
                name=overrides.get("name", f"Test Movie {uuid.uuid4().hex[:4]}_{i}"),
                year=overrides.get("year", 2020 + (i % 5)),
                time=overrides.get("time", 90 + i),
                imdb=overrides.get("imdb", 5.0 + (i % 5)),
                votes=overrides.get("votes", 1000 + i * 10),
                meta_score=overrides.get("meta_score", 50.0 + i),
                gross=overrides.get("gross", 100.0 + i),
                description=overrides.get("description", f"Test description {i}"),
                price=overrides.get("price", Decimal("9.99")),
                certification_id=certification.id,
            )
            movie.genres.extend(genres)
            movie.directors.extend(directors)
            movie.stars.extend(stars)
            movies.append(movie)

        db_session.add_all(movies)
        await db_session.commit()

        for movie in movies:
            await db_session.refresh(movie)

        return movies

    return _create_movies
