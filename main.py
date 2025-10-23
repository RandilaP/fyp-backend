from fastapi import FastAPI
from api import user_crud

app = FastAPI()

app.include_router(user_crud.router, prefix="/api", tags=["users"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)