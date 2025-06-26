from fastapi import FastAPI
from fastapi.websockets import WebSocket
import asyncio
import json

# Import routers and services
from app.routes import jobs
from app.services.database import SessionLocal, init_db

app = FastAPI(
    title="Task Queue System",
    description="A task queue system for handling background jobs.",
    version="1.0.0",
)


# Include routers
app.include_router(jobs.router, prefix="", tags=["jobs"])


@app.get("/")
async def root():
    return {"message": "Welcome to the Task Queue System API. Check /docs for API documentation."}

# Placeholder for WebSocket endpoint for real-time updates


@app.websocket("/jobs/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Simulate sending updates (to be replaced with actual job status updates)
            await websocket.send_text(json.dumps({"status": "connected", "message": "Waiting for job updates..."}))
            await asyncio.sleep(10)
    except Exception as e:
        await websocket.close()
        print(f"WebSocket error: {e}")

# Add event handlers for startup and shutdown


@app.on_event("startup")
async def startup_db_client():
    # Initialize database by creating tables if they don't exist
    init_db()


@app.on_event("shutdown")
async def shutdown_db_client():
    # Close database connections or other cleanup tasks
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
