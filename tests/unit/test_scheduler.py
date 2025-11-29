"""
Tests for Scheduler
"""

import pytest
from cell_os.scheduler import Scheduler, Resource, Task

class TestScheduler:
    
    def test_basic_scheduling(self):
        """Test basic dependency and resource constraints."""
        resources = [
            Resource(id="robot", name="Liquid Handler", capacity=1),
            Resource(id="incubator", name="Incubator", capacity=10)
        ]
        
        # Workflow 1
        t1 = Task(id="t1_prep", name="Prep 1", duration_min=10, resources_required=["robot"])
        t2 = Task(id="t2_inc", name="Incubate 1", duration_min=60, resources_required=["incubator"], predecessors=["t1_prep"])
        t3 = Task(id="t3_analyze", name="Analyze 1", duration_min=20, resources_required=["robot"], predecessors=["t2_inc"])
        
        # Workflow 2 (Parallel)
        t4 = Task(id="t4_prep", name="Prep 2", duration_min=10, resources_required=["robot"])
        t5 = Task(id="t5_inc", name="Incubate 2", duration_min=60, resources_required=["incubator"], predecessors=["t4_prep"])
        
        tasks = [t1, t2, t3, t4, t5]
        
        scheduler = Scheduler(resources)
        results = scheduler.schedule(tasks)
        
        assert len(results) == 5
        
        # Convert to dict for easy lookup
        sched = {r.task_id: r for r in results}
        
        # Check dependencies
        assert sched["t2_inc"].start_time >= sched["t1_prep"].end_time
        assert sched["t3_analyze"].start_time >= sched["t2_inc"].end_time
        assert sched["t5_inc"].start_time >= sched["t4_prep"].end_time
        
        # Check resource contention (Robot capacity 1)
        # t1, t3, t4 all use robot. None should overlap.
        robot_tasks = [sched["t1_prep"], sched["t3_analyze"], sched["t4_prep"]]
        for i in range(len(robot_tasks)):
            for j in range(i + 1, len(robot_tasks)):
                t_a = robot_tasks[i]
                t_b = robot_tasks[j]
                # Check for overlap: start_a < end_b AND start_b < end_a
                overlap = (t_a.start_time < t_b.end_time) and (t_b.start_time < t_a.end_time)
                assert not overlap, f"Robot tasks {t_a.task_id} and {t_b.task_id} overlap!"
                
    def test_capacity_constraint(self):
        """Test that capacity > 1 allows overlap."""
        resources = [
            Resource(id="incubator", name="Incubator", capacity=2)
        ]
        
        # 3 tasks, capacity 2. At least one must be delayed if they all start at 0.
        # But here we just check if 2 CAN overlap.
        t1 = Task(id="t1", name="Inc 1", duration_min=60, resources_required=["incubator"])
        t2 = Task(id="t2", name="Inc 2", duration_min=60, resources_required=["incubator"])
        
        tasks = [t1, t2]
        scheduler = Scheduler(resources)
        results = scheduler.schedule(tasks)
        
        sched = {r.task_id: r for r in results}
        
        # Since capacity is 2, they SHOULD be able to run in parallel (start at same time)
        # to minimize makespan (which would be 60).
        # If they were sequential, makespan would be 120.
        
        max_end = max(r.end_time for r in results)
        assert max_end == 60
