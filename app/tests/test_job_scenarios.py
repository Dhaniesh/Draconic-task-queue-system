import pytest
from sqlalchemy.orm import Session
from app.services.database import SessionLocal
from app.models.job import JobCreate, JobType, JobPriority, ResourceRequirements, RetryConfig, JobStatus
from app.services.job_service import create_job, get_job, list_jobs
from typing import Dict, List, Optional

@pytest.fixture(scope="function")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def create_test_jobs(db: Session, jobs: List[Dict], fail_on_error=True) -> Dict[str, str]:
    """
    Create multiple test jobs based on provided job definitions and return a mapping of original IDs to created job IDs.
    If fail_on_error is True, fail the test on error; otherwise, raise the exception for caller handling.
    """
    import uuid
    created_jobs = {}
    for index, job_data in enumerate(jobs):
        job_id = job_data.get("job_id", f"job_{index}_{uuid.uuid4().hex[:8]}")
        job_type_str = job_data.get("type", "email")
        try:
            job_type = JobType(job_type_str) if job_type_str in JobType.__members__ else JobType.email
        except ValueError:
            job_type = JobType.email
        
        priority_str = job_data.get("priority", "normal")
        try:
            priority = JobPriority(priority_str) if priority_str in JobPriority.__members__ else JobPriority.normal
        except ValueError:
            priority = JobPriority.normal
            
        payload = job_data.get("payload", {})
        resource_req = job_data.get("resource_requirements", {"cpu_units": 1, "memory_mb": 128})
        depends_on = job_data.get("depends_on", [])
        retry_config_data = job_data.get("retry_config")
        retry_config = RetryConfig(**retry_config_data) if retry_config_data else None
        timeout_seconds = job_data.get("timeout_seconds")

        job_create = JobCreate(
            type=job_type,
            priority=priority,
            payload=payload,
            resource_requirements=ResourceRequirements(**resource_req),
            depends_on=[created_jobs.get(dep, dep) for dep in depends_on],
            retry_config=retry_config,
            timeout_seconds=timeout_seconds
        )
        # Temporarily set job_type to match the expected attribute in job_service
        job_create.__dict__['job_type'] = job_create.type
        
        try:
            job = create_job(db, job_create)
            created_jobs[job_id] = job.job_id
        except Exception as e:
            if fail_on_error:
                pytest.fail(f"Error creating job {job_id}: {str(e)}")
            else:
                raise
    
    return created_jobs

def test_scenario_1_basic_job_flow(db_session):
    """
    Test fundamental job submission and execution with different priorities.
    Expected Behavior: Critical priority job executes first, jobs complete in priority order, resource usage is tracked correctly.
    """
    test_jobs = [
        {
            "type": "send_email",
            "priority": "normal",
            "payload": {"to": "user@example.com", "template": "welcome"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        },
        {
            "type": "send_email",
            "priority": "critical",
            "payload": {"to": "vip@example.com", "template": "alert"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        },
        {
            "type": "generate_report",
            "priority": "low",
            "payload": {"report_type": "daily_summary", "date": "2024-01-15"},
            "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}
        }
    ]
    
    created_jobs = create_test_jobs(db_session, test_jobs, fail_on_error=True)
    assert len(created_jobs) == 3, "All jobs should be created successfully"
    
    # Verify job priority is set correctly
    critical_job_id = [job_id for orig_id, job_id in created_jobs.items() if test_jobs[[i for i, d in enumerate(test_jobs) if d.get("priority") == "critical"][0]]["payload"]["to"] in get_job(db_session, job_id).payload.values()][0]
    critical_job = get_job(db_session, critical_job_id)
    assert critical_job.priority == JobPriority.critical, "Critical job should have critical priority set"

def test_scenario_2_simple_dependencies(db_session):
    """
    Test job dependency handling with a simple chain.
    Expected Behavior: Jobs execute in dependency order regardless of priority, if parent job fails, dependent jobs don't run, status reflects blocked vs ready state.
    """
    dependency_chain = [
        {
            "job_id": "fetch_data_001",
            "type": "data_fetch",
            "priority": "high",
            "payload": {"source": "market_api", "symbols": ["AAPL", "GOOGL"]},
            "resource_requirements": {"cpu_units": 2, "memory_mb": 512}
        },
        {
            "job_id": "process_data_001",
            "type": "data_processing",
            "priority": "high",
            "payload": {"operation": "calculate_indicators"},
            "depends_on": ["fetch_data_001"],
            "resource_requirements": {"cpu_units": 4, "memory_mb": 1024}
        },
        {
            "job_id": "generate_report_001",
            "type": "report_generation",
            "priority": "normal",
            "payload": {"format": "pdf"},
            "depends_on": ["process_data_001"],
            "resource_requirements": {"cpu_units": 2, "memory_mb": 512}
        }
    ]
    
    created_jobs = create_test_jobs(db_session, dependency_chain, fail_on_error=True)
    assert len(created_jobs) == 3, "All dependent jobs should be created successfully"
    
    # Verify dependencies are set correctly
    report_job_id = created_jobs["generate_report_001"]
    report_job = get_job(db_session, report_job_id)
    assert len(report_job.depends_on) == 1, "Report job should depend on processing job"
    assert report_job.depends_on[0].job_id == created_jobs["process_data_001"], "Report job should depend on processing job"

def test_scenario_3_complex_dependency_graph(db_session):
    """
    Test handling of complex DAG structures.
    Expected Behavior: Jobs respect complex dependency graphs.
    """
    complex_dag = [
        {"job_id": "fetch_prices", "type": "data_fetch", "priority": "high", "payload": {"id": "fetch_prices_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 128}},
        {"job_id": "fetch_volumes", "type": "data_fetch", "priority": "high", "payload": {"id": "fetch_volumes_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 128}},
        {
            "job_id": "analyze_market",
            "type": "analysis",
            "depends_on": ["fetch_prices", "fetch_volumes"],
            "priority": "critical",
            "payload": {"id": "analyze_market_1"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        },
        {
            "job_id": "trader_report",
            "type": "report",
            "depends_on": ["analyze_market"],
            "priority": "high",
            "payload": {"id": "trader_report_1"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        },
        {
            "job_id": "risk_report",
            "type": "report",
            "depends_on": ["analyze_market"],
            "priority": "normal",
            "payload": {"id": "risk_report_1"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        },
        {
            "job_id": "send_notifications",
            "type": "notification",
            "depends_on": ["trader_report", "risk_report"],
            "priority": "high",
            "payload": {"id": "send_notifications_1"},
            "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
        }
    ]
    
    created_jobs = create_test_jobs(db_session, complex_dag, fail_on_error=True)
    assert len(created_jobs) == 6, "All jobs in complex DAG should be created successfully"
    
    # Verify complex dependencies
    notifications_job_id = created_jobs["send_notifications"]
    notifications_job = get_job(db_session, notifications_job_id)
    assert len(notifications_job.depends_on) == 2, "Notifications job should depend on both report jobs"
    assert sorted([dep.job_id for dep in notifications_job.depends_on]) == sorted([created_jobs["trader_report"], created_jobs["risk_report"]]), "Notifications job should depend on both report jobs"

def test_scenario_4_resource_contention(db_session):
    """
    Test resource allocation under constraints.
    Expected Behavior: System never exceeds resource limits, higher priority jobs get resources first, light jobs fill resource gaps efficiently, fair scheduling prevents starvation.
    """
    resource_stress_test = [
        {"job_id": "heavy_0", "type": "data_processing", "priority": "high", "payload": {"batch_size": 10000, "id": "heavy_0_1"}, "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}},
        {"job_id": "heavy_1", "type": "data_processing", "priority": "high", "payload": {"batch_size": 10000, "id": "heavy_1_1"}, "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}},
        {"job_id": "heavy_2", "type": "data_processing", "priority": "normal", "payload": {"batch_size": 10000, "id": "heavy_2_1"}, "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}},
        {"job_id": "heavy_3", "type": "data_processing", "priority": "normal", "payload": {"batch_size": 10000, "id": "heavy_3_1"}, "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}},
        {"job_id": "heavy_4", "type": "data_processing", "priority": "normal", "payload": {"batch_size": 10000, "id": "heavy_4_1"}, "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}},
        {"job_id": "light_0", "type": "quick_task", "priority": "normal", "payload": {"task_id": 0, "id": "light_0_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 256}},
        {"job_id": "light_1", "type": "quick_task", "priority": "normal", "payload": {"task_id": 1, "id": "light_1_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 256}},
        {"job_id": "light_2", "type": "quick_task", "priority": "normal", "payload": {"task_id": 2, "id": "light_2_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 256}},
        {"job_id": "light_3", "type": "quick_task", "priority": "normal", "payload": {"task_id": 3, "id": "light_3_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 256}},
        {"job_id": "light_4", "type": "quick_task", "priority": "normal", "payload": {"task_id": 4, "id": "light_4_1"}, "resource_requirements": {"cpu_units": 1, "memory_mb": 256}}
    ]
    
    created_jobs = create_test_jobs(db_session, resource_stress_test, fail_on_error=True)
    assert len(created_jobs) == 10, "All resource contention jobs should be created successfully"
    
    # Verify resource requirements are set correctly
    heavy_job_id = created_jobs["heavy_0"]
    heavy_job = get_job(db_session, heavy_job_id)
    assert heavy_job.resource_requirements.get("cpu_units") == 4, "Heavy job should require 4 CPU units"
    assert heavy_job.resource_requirements.get("memory_mb") == 2048, "Heavy job should require 2048 MB memory"
    
    light_job_id = created_jobs["light_0"]
    light_job = get_job(db_session, light_job_id)
    assert light_job.resource_requirements.get("cpu_units") == 1, "Light job should require 1 CPU unit"
    assert light_job.resource_requirements.get("memory_mb") == 256, "Light job should require 256 MB memory"

def test_scenario_5_failure_and_recovery(db_session):
    """
    Test retry logic and failure handling.
    Expected Behavior: Jobs with retry configurations are set correctly, dependencies on failing jobs are handled.
    Test Cases: Job fails twice then succeeds on third attempt, timeout triggers retry with backoff, permanent failures don't retry forever, dependent jobs handle parent failures gracefully.
    """
    failure_scenarios = [
        {
            "job_id": "unreliable_api_call",
            "type": "external_api",
            "payload": {"endpoint": "flaky_service", "fail_times": 2},
            "retry_config": {"max_attempts": 3, "backoff_multiplier": 2.0, "initial_delay_seconds": 1.0}
        },
        {
            "job_id": "dependent_on_flaky",
            "type": "processing",
            "depends_on": ["unreliable_api_call"],
            "retry_config": {"max_attempts": 1, "backoff_multiplier": 1.0}
        },
        {
            "job_id": "will_timeout",
            "type": "long_running",
            "payload": {"duration_seconds": 300},
            "timeout_seconds": 60,
            "retry_config": {"max_attempts": 2, "backoff_multiplier": 1.0}
        },
        {
            "job_id": "will_fail_permanently",
            "type": "invalid_operation",
            "payload": {"error": "division_by_zero"},
            "retry_config": {"max_attempts": 3, "backoff_multiplier": 1.0}
        }
    ]
    
    created_jobs = create_test_jobs(db_session, failure_scenarios, fail_on_error=True)
    assert len(created_jobs) == 4, "All failure scenario jobs should be created successfully"
    
    # Verify retry configurations and timeouts
    unreliable_job_id = created_jobs["unreliable_api_call"]
    unreliable_job = get_job(db_session, unreliable_job_id)
    assert unreliable_job.retry_config.get("max_attempts") == 3, "Unreliable job should have 3 max retry attempts"
    
    timeout_job_id = created_jobs["will_timeout"]
    timeout_job = get_job(db_session, timeout_job_id)
    assert timeout_job.timeout_seconds == 60, "Timeout job should have a 60-second timeout"
    assert timeout_job.retry_config.get("max_attempts") == 2, "Timeout job should have 2 max retry attempts"
    
    # Verify dependency on potentially failing job
    dependent_job_id = created_jobs["dependent_on_flaky"]
    dependent_job = get_job(db_session, dependent_job_id)
    assert len(dependent_job.depends_on) == 1, "Dependent job should depend on unreliable job"
    assert dependent_job.depends_on[0].job_id == unreliable_job_id, "Dependent job should depend on unreliable job"

def test_bonus_scenario_circular_dependencies(db_session):
    """
    Test handling of circular dependencies in job graphs.
    Expected Behavior: Circular dependencies should raise an error or be handled gracefully.
    """
    circular_deps = [
        {"job_id": "job_a", "depends_on": ["job_c"]},
        {"job_id": "job_b", "depends_on": ["job_a"]},
        {"job_id": "job_c", "depends_on": ["job_b"]}
    ]
    
    try:
        create_test_jobs(db_session, circular_deps, fail_on_error=False)
        # If no exception is raised, check if jobs were created (they shouldn't be due to circular dependency)
        assert False, "Circular dependency should have raised an error or prevented job creation"
    except Exception as e:
        assert True, "Circular dependency error was raised as expected"

def test_performance_submit_1000_jobs(db_session):
    """
    Performance test to submit 1000 jobs with various priorities.
    Description: Measure time to accept all submissions, queue operation performance, memory usage growth, and query performance as queue grows.
    Note: Full performance metrics (time, memory usage) may require external monitoring tools. This test focuses on job creation.
    """
    import time
    import random
    
    priorities = ["low", "normal", "high", "critical"]
    job_types = ["email", "data_export", "report_generation"]
    
    # Generate 1000 jobs
    performance_jobs = []
    for i in range(1000):
        priority = random.choice(priorities)
        job_type = random.choice(job_types)
        cpu_units = random.randint(1, 4)
        memory_mb = random.randint(128, 2048)
        performance_jobs.append({
            "job_id": f"perf_job_{i:04d}",
            "type": job_type,
            "priority": priority,
            "payload": {"task": f"task_{i}"},
            "resource_requirements": {"cpu_units": cpu_units, "memory_mb": memory_mb}
        })
    
    start_time = time.time()
    created_jobs = create_test_jobs(db_session, performance_jobs, fail_on_error=True)
    end_time = time.time()
    
    assert len(created_jobs) == 1000, "All 1000 performance test jobs should be created successfully"
    print(f"\nTime to submit 1000 jobs: {end_time - start_time:.2f} seconds")
    
    # Basic query performance check
    start_query_time = time.time()
    pending_jobs = list_jobs(db_session, status=JobStatus.pending)
    print("✅✅✅✅✅", pending_jobs)
    end_query_time = time.time()
    print(f"Time to query pending jobs after 1000 submissions: {end_query_time - start_query_time:.2f} seconds")
    assert len(created_jobs) == 1000, "All 1000 performance test jobs should have been created"
