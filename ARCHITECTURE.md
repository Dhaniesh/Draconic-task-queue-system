# Architecture Overview: Task Queue System

This document summarizes the architectural decisions behind the implementation of a task queue system built with FastAPI. The system is designed to support background job execution for a real-time fintech platform, with an emphasis on scalability, reliability, and performance.

## System Components

The task queue system is structured as a distributed application with the following key components:

* **FastAPI Application**: Provides APIs for job submission, status tracking, and real-time updates via WebSocket.
* **PostgreSQL Database**: Stores job metadata, dependencies, execution history, logs, and resource usage information.
* **Worker Process**: Executes jobs asynchronously, taking into account job priorities, dependencies, and system resource limits.
* **Docker Compose**: Used to orchestrate application and database services for local development and deployment.

## Technical Decisions

### 1. Job Model and Database Design

* **Job Metadata**: Each job is uniquely identified and includes attributes such as type, priority, status, payload, retry configuration, timeout settings, and timestamps (creation, update, completion).
* **Dependency Management**: A dedicated `job_dependencies` table models many-to-many relationships, supporting complex execution graphs by linking jobs to their prerequisites.
* **Execution Logs**: A `job_logs` table records execution attempts, status transitions, and logs to aid in debugging and monitoring.
* **Resource Allocation**: Resource usage (CPU and memory) is tracked either in memory or via a database table, depending on the environment.
* **Indexing**: Indexes are applied to high-traffic fields (e.g., `status`, `priority`, `created_at`) to support fast lookups and ensure the system scales as the job volume grows.

### 2. Scheduling Strategy

* **Priority-Based Execution**: Jobs are sorted by predefined priority levels (e.g., critical, high, normal, low). Workers process higher-priority jobs first using a priority queue.
* **Dependency Resolution**: Before a job runs, the system verifies that all dependent jobs have completed successfully. A graph traversal algorithm ensures dependencies are valid and acyclic.
* **Resource Awareness**: Jobs are executed only when sufficient resources are available, ensuring fair use and system stability.

### 3. Dependency Management

* **DAG Representation**: Job dependencies are modeled as a Directed Acyclic Graph (DAG). Jobs will only execute once their dependencies are complete.
* **Cycle Detection**: The system checks for cycles during job submission. Any detected cycle results in the job being rejected with an appropriate error message.

### 4. Resource Management

* **Allocation Policy**: Jobs are scheduled on a first-come, first-served basis, with respect to job priority. If resources are unavailable, jobs remain pending.
* **Tracking Mechanism**: While the current system uses in-memory tracking, future iterations could leverage Redis or a centralized service for distributed environments.

### 5. Failure Handling and Retry Logic

* **Retry Policy**: Jobs are retried based on configurable settings using exponential backoff to reduce system strain.
* **Permanent Failures**: After exceeding retry limits, jobs are marked as failed. These failures are logged for post-mortem analysis. A dead-letter queue is a potential future addition.
* **Timeouts**: Jobs that exceed a predefined execution time are terminated and marked as failed, triggering retries where applicable.

### 6. Idempotency

* **Duplicate Detection**: A unique identifier or hash is used to detect and prevent duplicate job submissions. If a similar job is already pending or running, the new request is rejected with a reference to the existing one.

### 7. Concurrency and Consistency

* **Async Execution**: The system uses `asyncio` to simulate concurrent job execution, optimizing resource utilization within defined constraints.
* **Transactional Safety**: Database transactions and locking ensure consistency when multiple processes attempt to modify the same job concurrently.

### 8. Graceful Shutdown

* **Termination Handling**: On shutdown, in-progress jobs are allowed to complete within a configurable grace period. No new jobs are started during this phase.

### 9. Monitoring and Metrics

* **Metrics Collection**: Basic operational metrics such as queue length, wait time, and failure rates are collected and exposed via API or logs.
* **Logging**: Execution and system logs are stored in the database and made accessible via the API for diagnostic purposes.

## Performance Considerations

* **Queue Efficiency**: Priority queue operations are optimized for performance using efficient data structures and indexed queries.
* **Data Growth**: As job volume increases, database partitioning or archiving may be introduced. For now, indexing ensures acceptable performance levels.
* **System Bottlenecks**: Known performance risks include database contention and resource tracking under heavy load. Potential mitigations include caching and distributed locks.

## Trade-offs and Practical Choices

* **Simplicity vs. Scalability**: In-memory resource tracking offers ease of development but limits scalability. A distributed solution is better suited for production environments.
* **Cycle Detection Overhead**: Verifying DAG validity during submission introduces some latency but helps maintain system correctness.
* **Worker Model**: Workers currently poll the database for available jobs. While simple, this model could be replaced by a publish/subscribe mechanism (e.g., Redis, RabbitMQ) for better responsiveness.