# Analytics and Job Queue System

## Overview

cell_OS now includes advanced features for managing workflow executions at scale: a **Job Queue System** for scheduling and prioritization, and **Enhanced Analytics** for operational insights.

## Job Queue System

The Job Queue System allows you to schedule protocols, manage priorities, and ensure efficient resource utilization.

### Key Features

- **Priority Scheduling**: Assign priority levels (Low, Normal, High, Urgent) to jobs. Urgent jobs are processed first.
- **Scheduled Execution**: Schedule protocols to run at a specific future time.
- **Resource Locking**: Prevents multiple jobs from accessing the same hardware resource simultaneously (e.g., OT-2 robot).
- **Persistence**: All jobs are stored in a SQLite database (`data/job_queue.db`), ensuring no data loss on restart.

### Usage

#### Submitting a Job

In the **Execution Monitor** tab:
1. Select your protocol parameters (Cell Line, Vessel, Operation).
2. Check "Schedule for later" if you want to delay execution.
3. Select a Priority level.
4. Click "📅 Add to Queue".

#### Monitoring the Queue

Navigate to the **📋 Job Queue** sub-tab in the Execution Monitor to view:
- List of queued and scheduled jobs.
- Current status of each job.
- Queue statistics (total queued, running, completed).

### Programmatic Usage

```python
from cell_os.job_queue import JobQueue, JobPriority

# Initialize
queue = JobQueue()

# Submit a job
job = queue.submit_job(
    execution_id="exec-123",
    priority=JobPriority.HIGH,
    scheduled_time=datetime.now() + timedelta(hours=2)
)

# Check status
status = queue.get_job_status(job.job_id)
```

## Enhanced Analytics

The **Analytics** tab provides deep insights into your laboratory operations.

### Key Metrics

- **Success Rate**: Percentage of successfully completed protocols.
- **Average Duration**: Mean time taken for protocols to complete.
- **Execution Volume**: Trends in protocol execution over time.

### Visualizations

- **Status Distribution**: Pie chart showing the ratio of Completed vs. Failed vs. Running jobs.
- **Daily Volume**: Bar chart of executions per day.
- **Cell Line Activity**: Breakdown of which cell lines are being processed most frequently.
- **Protocol Performance**: Detailed table showing success rates and average durations for each operation type (Thaw, Passage, Feed).

### Benefits

- **Optimize Operations**: Identify bottlenecks or frequently failing protocols.
- **Resource Planning**: Understand peak usage times and most used cell lines.
- **Cost Analysis**: (Future) Correlate execution data with reagent costs.

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Dashboard UI   │ ---> │    Job Queue    │ ---> │ Workflow Exec.  │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                  │                        │
                                  v                        v
                         ┌─────────────────┐      ┌─────────────────┐
                         │  Job Database   │      │ Execution DB    │
                         │ (job_queue.db)  │      │ (executions.db) │
                         └─────────────────┘      └─────────────────┘
                                  │                        │
                                  └──────────┬─────────────┘
                                             │
                                             v
                                    ┌─────────────────┐
                                    │    Analytics    │
                                    │    Dashboard    │
                                    └─────────────────┘
```

## Future Enhancements

- **Worker Pools**: Support for multiple concurrent workers/robots.
- **Advanced Resource Management**: Fine-grained locking for specific modules (e.g., centrifuge vs. liquid handler).
- **Predictive Analytics**: ML-based prediction of protocol completion times and failure risks.
