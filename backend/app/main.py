from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import process_slides, clear, documents, debug, admin, pathway, query

app = FastAPI(title=settings.APP_NAME)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(process_slides.router)
app.include_router(clear.router)
app.include_router(documents.router)
app.include_router(debug.router)
app.include_router(admin.router)
app.include_router(pathway.router)
app.include_router(query.router)
from app.routers import invest
app.include_router(invest.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
