from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Change Order Generator API",
    description="API for generating construction change orders",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint showing API status."""
    return {
        "status": "online",
        "message": "Change Order Generator API is running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": {
            "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
            "firebase_bucket_configured": bool(os.getenv("FIREBASE_STORAGE_BUCKET"))
        }
    } 