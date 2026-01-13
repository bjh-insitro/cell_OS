import os
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

from run_loop import run_campaign

def test_loop_execution():
    print("Starting loop verification...")
    config = {
        "initial_budget": 500,
        "max_steps": 2,  # Short run
        "cell_lines": ["U2OS", "HepG2"],
        "compounds": ["staurosporine", "tunicamycin"],
        "dose_grid": [1e-3, 1e-2, 1e-1, 1.0, 10.0],
        "reward": {
            "objective": "viability",
            "mode": "balanced"
        }
    }
    
    try:
        history = run_campaign(config)
        print("Loop executed successfully!")
        print(f"History length: {len(history) if hasattr(history, '__len__') else 'Unknown'}")
    except Exception as e:
        print(f"Loop failed with error: {e}")
        raise e

if __name__ == "__main__":
    test_loop_execution()
