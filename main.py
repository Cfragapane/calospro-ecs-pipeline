from fastapi import FastAPI
import os

app = FastAPI(title="Calos Containerized App")

# CALOSPRO-50: Der Health-Endpoint für AWS ECS
@app.get("/health", status_code=200)
async def health_check():
    return {"status": "healthy", "environment": os.getenv("ENV", "production")}

@app.get("/")
async def root():
    return {"message": "Hallo aus dem neuen ECS-Projekt!"}
