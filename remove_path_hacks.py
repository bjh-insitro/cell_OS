#!/usr/bin/env python3
"""
Remove sys.path.append() hacks from test files.

These are no longer needed since the package is properly installed.
"""

import os
import re
from pathlib import Path

def remove_sys_path_hacks(file_path):
    """Remove sys.path.append lines and related imports from a Python file."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    skip_next = False
    changes_made = False
    
    for i, line in enumerate(lines):
        # Skip lines with sys.path.append
        if 'sys.path.append' in line or 'sys.path.insert' in line:
            changes_made = True
            continue
            
        # Skip import sys if it's only used for path manipulation
        if line.strip() == 'import sys' and i + 1 < len(lines):
            # Check if next few lines use sys.path
            next_lines = ''.join(lines[i+1:min(i+5, len(lines))])
            if 'sys.path' in next_lines and 'sys.exit' not in next_lines:
                changes_made = True
                continue
        
        # Skip import os if only used for path manipulation
        if line.strip() == 'import os' and i + 1 < len(lines):
            next_lines = ''.join(lines[i+1:min(i+10, len(lines))])
            if 'os.path.abspath' in next_lines and 'sys.path' in next_lines:
                # Check if os is used for anything else
                rest_of_file = ''.join(lines[i+10:])
                if 'os.' not in rest_of_file or rest_of_file.count('os.') < 2:
                    changes_made = True
                    continue
        
        new_lines.append(line)
    
    if changes_made:
        with open(file_path, 'w') as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    test_dir = Path('tests')
    files_modified = []
    
    for py_file in test_dir.rglob('*.py'):
        if remove_sys_path_hacks(py_file):
            files_modified.append(str(py_file))
            print(f"✓ Cleaned {py_file}")
    
    print(f"\n✅ Modified {len(files_modified)} files")
    for f in files_modified:
        print(f"  - {f}")

if __name__ == "__main__":
    main()
