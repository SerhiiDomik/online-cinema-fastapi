# Online Cinema (FastAPI)

## Project Overview

**Online Cinema** is a FastAPI-based platform that allows users to browse movie information, save favorites, comment, react, rate, and interact in a forum-like environment. The application uses JWT authentication, user roles, asynchronous tasks via Celery, and is fully containerized with Docker.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Poetry
- Git

### Local Setup

```bash
# Clone the repository
git clone https://github.com/SerhiiDomik/online-cinema-fastapi.git
cd <repo>

# Copy and create environment variables
cp .env.sample .env
cp docker/nginx/.env.sample docker/nginx/.env

# Install dependencies
docker-compose -f docker-compose-dev.yml run --rm api poetry install

# Build and start services
docker-compose -f docker-compose-dev.yml up --build
```


## Project Structure
```bash
.env
.env.sample
.flake8
.gitignore
alembic.ini
docker-compose-dev.yml
docker-compose-prod.yml
docker-compose-tests.yml
Dockerfile
poetry.lock
project_structure.txt
pyproject.toml
pytest.ini
README.md
__init__.py

.github/
└── workflows/
    ├── cd-pipeline.yml
    └── ci-pipeline.yml

commands/
├── deploy.sh
├── run_migration.sh
├── run_web_server_dev.sh
├── run_web_server_prod.sh
├── setup_mailhog_auth.sh
├── setup_minio.sh
└── set_nginx_basic_auth.sh

configs/
└── nginx/
    └── nginx.conf

docker/
├── mailhog/Dockerfile
├── minio_mc/Dockerfile
├── nginx/
│   ├── .env
│   ├── .env.sample
│   └── Dockerfile
└── tests/Dockerfile

init.sql

src/
├── main.py
├── celery_task/
│   ├── app.py
│   ├── tasks.py
│   └── __init__.py
├── config/
│   ├── dependencies.py
│   ├── settings.py
│   └── __init__.py
├── database/
│   ├── session_postgresql.py
│   ├── session_sqlite.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── README
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 4c30519e903c_initial.py
│   │       ├── 9b4eac5d3af5_temp_migration.py
│   │       └── ce3f0a317cf6_temp_migration.py
│   └── models/
│       ├── base.py
│   │   ├── movies.py
│   │   └── users.py
│   └── __init__.py
├── validators/
│   ├── users.py
│   └── __init__.py
├── exceptions/
│   ├── email.py
│   ├── security.py
│   ├── storage.py
│   └── __init__.py
├── notifications/
│   ├── emails.py
│   ├── interfaces.py
│   ├── templates/
│   │   ├── activation_complete.html
│   │   ├── activation_request.html
│   │   ├── comment_reaction.html
│   │   ├── comment_reply.html
│   │   ├── password_reset_complete.html
│   │   └── password_reset_request.html
│   └── __init__.py
├── routes/
│   ├── dependencies.py
│   ├── genres.py
│   ├── users.py
│   └── movies/
│       ├── comments.py
│       ├── favorite_movies.py
│       └── movies.py
├── schemas/
│   ├── movies.py
│   └── users.py
├── security/
│   ├── http.py
│   ├── interfaces.py
│   ├── passwords.py
│   ├── token_manager.py
│   ├── utils.py
│   └── __init__.py
├── storages/
│   ├── interfaces.py
│   ├── s3.py
│   └── __init__.py
└── tests/
    ├── conftest.py
    ├── doubles/
    ├── fakes/
    ├── stubs/
    ├── test_e2e/
    └── test_integration/
```

## Architecture & Stack

- **FastAPI**: high-performance API framework  
- **PostgreSQL**: relational database  
- **Redis + Celery + celery-beat**: async tasks & scheduled cleanup of expired tokens  
- **MinIO**: S3-compatible object storage for avatars  
- **JWT**: authentication (access & refresh tokens)  
- **Docker & Docker Compose**: containerization of API, DB, Redis, Celery, MinIO, and more  
- **Poetry**: dependency & environment management  
- **GitHub Actions**: CI/CD pipelines for linting, testing, and deployment

## Core Features

- **Authentication & Authorization**:
  - Email registration & activation link (24h validity) with resend option
  - JWT-based access & refresh tokens; logout revokes refresh token
  - Password reset via email token; change password with complexity checks
  - User roles: `USER`, `MODERATOR`, `ADMIN`

- **Movie Catalog & Forum**:
  - Browse movies with pagination, filters, sorting, and search
  - Save movies to **favorites** (favorite_movies) with full catalog functionality
  - Rate movies on a 10-point scale
  - Comment on movies, react (like/dislike), and reply to comments
  - Email notifications on comment replies & reactions

## Running the Application

```bash
docker-compose -f docker-compose-dev.yml up --build
```

## CI/CD with GitHub Actions

- **Automated Processes**: 
Configure GitHub Actions to automate code quality checks, testing, and deployment pipelines.

- **Code Quality Checks**: 
Run linters: flake8, black

- **Continuous Deployment**:
Automatically deploy on merge to AWS EC2 via GitHub Actions workflows

## Testing

**Integration tests:** pytest-based tests covering API endpoints & DB interactions

```bash
pytest .\src\tests\test_integration\
```

**End-to-End tests:** full workflow tests (e.g., registration email, comment notifications)

```bash
docker-compose -f docker-compose-tests.yml up  --build    
```

## API Documentation

Interactive docs available at /docs (Swagger/OpenAPI v3) for authorized users.

Visit http://localhost:8000/docs
