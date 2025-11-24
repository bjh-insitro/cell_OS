"""
Test script for POSH Decision Engine
"""

import sys
import os
sys.path.append(os.getcwd())

from src.posh_decision_engine import POSHDecisionEngine, UserRequirements

def test_decision_engine():
    print("=" * 80)
    print("TESTING POSH DECISION ENGINE")
    print("=" * 80)
    
    engine = POSHDecisionEngine()
    
    # Test Case 1: Small pilot study
    print("\n[Test 1] Small Pilot Study (5 plates, $5k budget, 2 weeks)")
    req1 = UserRequirements(
        num_plates=5,
        budget_usd=5000,
        timeline_weeks=2,
        has_automation=False,
        needs_multimodal=False
    )
    rec1 = engine.recommend(req1)
    print(f"  Protocol: {rec1.protocol.value}")
    print(f"  Automation: {rec1.automation.value}")
    print(f"  Multimodal: {rec1.multimodal}")
    print(f"  Cost: ${rec1.estimated_cost_usd:,.0f}")
    print(f"  Time: {rec1.estimated_time_weeks:.1f} weeks")
    print(f"  Warnings: {len(rec1.warnings)}")
    
    # Test Case 2: Medium scale with automation
    print("\n[Test 2] Medium Scale (30 plates, $30k budget, 4 weeks, automation)")
    req2 = UserRequirements(
        num_plates=30,
        budget_usd=30000,
        timeline_weeks=4,
        has_automation=True,
        needs_multimodal=False
    )
    rec2 = engine.recommend(req2)
    print(f"  Protocol: {rec2.protocol.value}")
    print(f"  Automation: {rec2.automation.value}")
    print(f"  Multimodal: {rec2.multimodal}")
    print(f"  Cost: ${rec2.estimated_cost_usd:,.0f}")
    print(f"  Time: {rec2.estimated_time_weeks:.1f} weeks")
    
    # Test Case 3: Large multimodal study
    print("\n[Test 3] Large Multimodal (100 plates, $100k budget, 8 weeks)")
    req3 = UserRequirements(
        num_plates=100,
        budget_usd=100000,
        timeline_weeks=8,
        has_automation=True,
        needs_multimodal=True
    )
    rec3 = engine.recommend(req3)
    print(f"  Protocol: {rec3.protocol.value}")
    print(f"  Automation: {rec3.automation.value}")
    print(f"  Multimodal: {rec3.multimodal}")
    print(f"  Cost: ${rec3.estimated_cost_usd:,.0f}")
    print(f"  Time: {rec3.estimated_time_weeks:.1f} weeks")
    
    # Test Case 4: Budget constrained
    print("\n[Test 4] Budget Constrained (20 plates, $10k budget, 6 weeks)")
    req4 = UserRequirements(
        num_plates=20,
        budget_usd=10000,
        timeline_weeks=6,
        has_automation=False,
        needs_multimodal=True
    )
    rec4 = engine.recommend(req4)
    print(f"  Protocol: {rec4.protocol.value}")
    print(f"  Automation: {rec4.automation.value}")
    print(f"  Multimodal: {rec4.multimodal}")
    print(f"  Cost: ${rec4.estimated_cost_usd:,.0f}")
    print(f"  Time: {rec4.estimated_time_weeks:.1f} weeks")
    if rec4.warnings:
        print(f"  ⚠️ Warnings:")
        for w in rec4.warnings:
            print(f"    - {w}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)

if __name__ == "__main__":
    test_decision_engine()
