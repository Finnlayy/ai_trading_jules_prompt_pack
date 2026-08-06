from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
import os
os.environ["CORS_ORIGINS"] = ""
from app.core.config import CORS_ORIGINS
print("CORS_ORIGINS default:", CORS_ORIGINS)
