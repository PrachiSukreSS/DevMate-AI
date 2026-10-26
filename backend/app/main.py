"""Application entry point: assemble the HTTP application and its routes."""

# import FastAPI class from fastapi module to create an instance of the FastAPI application
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# import API router for health check endpoints from the app.api.health module and alias it as health_router
from app.api.action_plans import router as action_plans_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.questions import router as questions_router
from app.db.database import initialize_database

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield



app = FastAPI(  # to create main app object(app), it is entry point
    # pass api details and this will br shown on swagger ui documentation
    title="DevMate AI API",
    description="A learning-first assistant for investigating software projects.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
# register health_router in our main app , make availble at /health endpoint
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(projects_router)
app.include_router(questions_router)
app.include_router(action_plans_router)






