"""
Static analysis tests to catch common Python errors before runtime.
These tests use pylint and other static analysis tools to find issues that
unit tests might miss.
"""
import importlib.util
import py_compile
import subprocess
import tempfile
from pathlib import Path

import pytest
import os


class TestStaticAnalysis:
    """Static analysis tests for dashboard code."""
    
    def test_no_undefined_variables_in_dashboard(self):
        """Use pylint to check for undefined variables in dashboard files."""
        dashboard_dir = Path("dashboard_app")

        if importlib.util.find_spec("pylint") is None:
            pytest.skip("pylint not available in environment")
        
        # Run pylint on all Python files
        result = subprocess.run(
            [
                "python3", "-m", "pylint",
                "--disable=all",  # Disable all checks
                "--enable=undefined-variable,used-before-assignment",  # Only check for undefined vars
                "--score=no",  # Don't show score
                str(dashboard_dir)
            ],
            capture_output=True,
            text=True
        )
        
        # If pylint found issues, fail the test
        if result.returncode != 0:
            pytest.fail(
                f"Undefined variables found in dashboard:\n{result.stdout}\n{result.stderr}"
            )
    
    def test_no_syntax_errors_in_dashboard(self):
        """Check for Python syntax errors in all dashboard files."""
        dashboard_dir = Path("dashboard_app")
        errors = []
        cache_dir = Path(tempfile.mkdtemp())

        for py_file in dashboard_dir.rglob("*.py"):
            compiled_path = cache_dir / (py_file.stem + ".pyc")
            try:
                py_compile.compile(
                    str(py_file),
                    cfile=str(compiled_path),
                    doraise=True,
                )
            except py_compile.PyCompileError as exc:
                errors.append(f"{py_file}: {exc.msg}")
        
        if errors:
            pytest.fail(f"Syntax errors found:\n" + "\n".join(errors))
    
    def test_no_import_errors_in_dashboard(self):
        """Check that all dashboard files can be imported without errors."""
        dashboard_dir = Path("dashboard_app")
        errors = []
        
        for py_file in dashboard_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            # Convert path to module name
            module_path = py_file.with_suffix("")
            module_name = ".".join(module_path.parts)
            if any(not part.isidentifier() for part in module_path.parts):
                continue  # Skip files that cannot be imported as modules (numeric names)

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd())
            result = subprocess.run(
                ["python3", "-c", f"import {module_name}"],
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                errors.append(f"{module_name}: {result.stderr}")
        
        if errors:
            pytest.fail(f"Import errors found:\n" + "\n".join(errors))


class TestCodeQuality:
    """Code quality checks."""
    
    def test_no_unused_variables(self):
        """Check for unused variables that might indicate bugs."""
        dashboard_dir = Path("dashboard_app")
        
        result = subprocess.run(
            [
                "python3", "-m", "pylint",
                "--disable=all",
                "--enable=unused-variable,unused-argument",
                "--score=no",
                str(dashboard_dir)
            ],
            capture_output=True,
            text=True
        )
        
        # This is a warning, not a hard failure
        if "unused" in result.stdout.lower():
            print(f"Warning: Unused variables found:\n{result.stdout}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
