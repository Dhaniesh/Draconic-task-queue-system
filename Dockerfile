# base image
FROM python:3.9-slim

# Set working directory in the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code into the container
COPY . .

# Expose the port for the FastAPI application
EXPOSE 8000

# Command to run the application will be specified in docker-compose.yml
