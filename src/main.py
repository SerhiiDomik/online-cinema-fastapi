from fastapi import FastAPI

app = FastAPI(
    title="Online Cinema API",
    description="API for managing movies and user accounts",
    version="0.1.0"
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Online Cinema API"}
