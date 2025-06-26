# Task Queue System

A task queue system built with FastAPI for handling background jobs in a real-time fintech platform. This system supports job scheduling, prioritization, dependency management, and resource allocation.

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed on your machine.
- Python 3.9+ for local development (optional).

### Using Docker (Recommended)
1. Clone this repository and navigate to the `draconic-task-queue` directory.
2. Run the following command to start the services:
   ```
   docker-compose up --build
   ```
3. The FastAPI application will be available at `http://localhost:8000`.
4. Access the API documentation at `http://localhost:8000/docs`.

### Local Development
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Set up the PostgreSQL database and update the `DATABASE_URL` in your environment or `.env` file.
   ```
3. Start the FastAPI server:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Start the worker process in a separate terminal:
   ```
   python app/workers/worker.py
   ```

## API Endpoints
- **POST /jobs**: Submit a new job.
- **GET /jobs/{job_id}**: Get job status and details.
- **GET /jobs**: List jobs with filtering options.
- **PATCH /jobs/{job_id}/cancel**: Cancel a job if possible.
- **GET /jobs/{job_id}/logs**: Get job execution logs.
- **WS /jobs/stream**: WebSocket for real-time job updates.

## Project Structure
- `app/`: Contains the FastAPI application, models, routes, services, and workers.
- `tests/`: Unit and integration tests.
- `migrations/`: Database migration scripts using Alembic.
- `docker-compose.yml`: Configuration for Docker setup.
- `requirements.txt`: List of Python dependencies.
