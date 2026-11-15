"""Vercel entrypoint (Vercel looks for an `app` in index.py). Locally run: uvicorn backend.app:app"""
from backend.app import app  # noqa: F401
