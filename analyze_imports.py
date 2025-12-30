#!/usr/bin/env python3
"""
Analyze import dependencies in the cell_OS codebase.
"""
import ast
import os
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple
import json


class ImportAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.src_dir = self.root_dir / "src" / "cell_os"

        # Data structures for analysis
        self.imports_by_file: Dict[str, List[Dict]] = {}
        self.import_counts: Counter = Counter()
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.import_types: Dict[str, Dict] = {}  # Track relative vs absolute

    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        try:
            rel_path = file_path.relative_to(self.src_dir)
            parts = list(rel_path.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].replace(".py", "")
            return "cell_os." + ".".join(parts) if parts else "cell_os"
        except ValueError:
            # Not in src_dir
            return str(file_path)

    def parse_imports(self, file_path: Path) -> List[Dict]:
        """Parse all imports from a Python file."""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'type': 'import',
                            'module': alias.name,
                            'name': alias.asname or alias.name,
                            'relative': False,
                            'line': node.lineno
                        })

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    is_relative = node.level > 0

                    for alias in node.names:
                        imports.append({
                            'type': 'from',
                            'module': module,
                            'name': alias.name,
                            'alias': alias.asname,
                            'relative': is_relative,
                            'level': node.level,
                            'line': node.lineno
                        })
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

        return imports

    def is_cell_os_import(self, module_name: str) -> bool:
        """Check if import is from cell_os package."""
        return module_name.startswith('cell_os.') or module_name == 'cell_os'

    def analyze_file(self, file_path: Path):
        """Analyze imports in a single file."""
        module_name = self.get_module_name(file_path)
        imports = self.parse_imports(file_path)
        self.imports_by_file[str(file_path)] = imports

        # Track import statistics
        has_relative = False
        has_absolute = False

        for imp in imports:
            # Count cell_os imports
            if imp['type'] == 'import':
                if self.is_cell_os_import(imp['module']):
                    self.import_counts[imp['module']] += 1
                    self.dependency_graph[module_name].add(imp['module'])
                    self.reverse_dependency_graph[imp['module']].add(module_name)
                    has_absolute = not imp['relative']

            elif imp['type'] == 'from':
                full_module = imp['module']
                if imp['relative']:
                    # Resolve relative import
                    has_relative = True
                    # Simple resolution - may not be perfect
                    if imp['level'] == 1:
                        parent = '.'.join(module_name.split('.')[:-1])
                        full_module = parent + '.' + imp['module'] if imp['module'] else parent
                    elif imp['level'] == 2:
                        parent = '.'.join(module_name.split('.')[:-2])
                        full_module = parent + '.' + imp['module'] if imp['module'] else parent
                else:
                    has_absolute = True

                if self.is_cell_os_import(full_module):
                    self.import_counts[full_module] += 1
                    self.dependency_graph[module_name].add(full_module)
                    self.reverse_dependency_graph[full_module].add(module_name)

        # Track mixed import styles
        self.import_types[module_name] = {
            'has_relative': has_relative,
            'has_absolute': has_absolute,
            'total_imports': len(imports)
        }

    def find_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies using DFS."""
        cycles = []
        visited = set()
        rec_stack = []

        def dfs(node: str, path: List[str]):
            if node in rec_stack:
                # Found a cycle
                cycle_start = rec_stack.index(node)
                cycle = rec_stack[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.append(node)

            for neighbor in self.dependency_graph.get(node, []):
                dfs(neighbor, path + [neighbor])

            rec_stack.pop()

        for node in self.dependency_graph:
            if node not in visited:
                dfs(node, [node])

        # Deduplicate cycles (same cycle can be found from different starting points)
        unique_cycles = []
        seen_cycles = set()
        for cycle in cycles:
            # Normalize cycle representation
            min_idx = cycle.index(min(cycle))
            normalized = tuple(cycle[min_idx:-1])  # Exclude duplicate last element
            if normalized not in seen_cycles:
                seen_cycles.add(normalized)
                unique_cycles.append(cycle)

        return unique_cycles

    def find_long_chains(self, max_depth: int = 5) -> List[List[str]]:
        """Find long dependency chains."""
        long_chains = []

        def dfs(node: str, path: List[str], visited: Set[str]):
            if len(path) >= max_depth:
                long_chains.append(path[:])
                return

            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    dfs(neighbor, path + [neighbor], visited)
                    visited.remove(neighbor)

        for start_node in self.dependency_graph:
            dfs(start_node, [start_node], {start_node})

        return long_chains

    def analyze_all(self):
        """Analyze all Python files in src/cell_os."""
        print(f"Analyzing imports in {self.src_dir}")

        py_files = list(self.src_dir.rglob("*.py"))
        print(f"Found {len(py_files)} Python files")

        for file_path in py_files:
            self.analyze_file(file_path)

        print(f"Analyzed {len(self.imports_by_file)} files")

    def generate_report(self) -> str:
        """Generate comprehensive import analysis report."""
        lines = []
        lines.append("=" * 80)
        lines.append("CELL_OS IMPORT DEPENDENCY ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        lines.append("## SUMMARY")
        lines.append(f"Total modules analyzed: {len(self.imports_by_file)}")
        lines.append(f"Total unique dependencies: {len(self.import_counts)}")
        lines.append(f"Total dependency edges: {sum(len(deps) for deps in self.dependency_graph.values())}")
        lines.append("")

        # Top 10 most imported modules
        lines.append("## TOP 10 MOST IMPORTED MODULES (Dependency Hotspots)")
        lines.append("-" * 80)
        for module, count in self.import_counts.most_common(10):
            importers = self.reverse_dependency_graph.get(module, set())
            lines.append(f"{count:3d} imports | {module}")
            lines.append(f"     Used by {len(importers)} modules")
        lines.append("")

        # Circular dependencies
        lines.append("## CIRCULAR DEPENDENCIES")
        lines.append("-" * 80)
        cycles = self.find_circular_dependencies()
        if cycles:
            lines.append(f"Found {len(cycles)} circular dependency cycles:\n")
            for i, cycle in enumerate(cycles, 1):
                lines.append(f"Cycle {i}:")
                for j, module in enumerate(cycle):
                    if j < len(cycle) - 1:
                        lines.append(f"  {module}")
                        lines.append(f"    -> imports")
                    else:
                        lines.append(f"  {module} (completes cycle)")
                lines.append("")
        else:
            lines.append("No circular dependencies found! ✓")
        lines.append("")

        # Modules with excessive imports
        lines.append("## MODULES WITH EXCESSIVE IMPORTS (>20 imports)")
        lines.append("-" * 80)
        excessive = [(mod, info['total_imports'])
                     for mod, info in self.import_types.items()
                     if info['total_imports'] > 20]
        excessive.sort(key=lambda x: x[1], reverse=True)

        if excessive:
            for module, count in excessive:
                lines.append(f"{count:3d} imports | {module}")
                # Show what it depends on
                deps = self.dependency_graph.get(module, set())
                cell_os_deps = [d for d in deps if self.is_cell_os_import(d)]
                if cell_os_deps:
                    lines.append(f"     Cell_OS dependencies: {len(cell_os_deps)}")
        else:
            lines.append("No modules with >20 imports found ✓")
        lines.append("")

        # Import inconsistencies
        lines.append("## IMPORT STYLE INCONSISTENCIES (Mixed relative/absolute)")
        lines.append("-" * 80)
        mixed_style = [(mod, info) for mod, info in self.import_types.items()
                       if info['has_relative'] and info['has_absolute']]

        if mixed_style:
            lines.append(f"Found {len(mixed_style)} modules mixing relative and absolute imports:\n")
            for module, info in mixed_style[:20]:  # Show top 20
                lines.append(f"  {module}")
        else:
            lines.append("No mixed import styles found ✓")
        lines.append("")

        # Long dependency chains
        lines.append("## LONG DEPENDENCY CHAINS (5+ levels)")
        lines.append("-" * 80)
        chains = self.find_long_chains(max_depth=5)
        if chains:
            lines.append(f"Found {len(chains)} long dependency chains:\n")
            # Show a sample
            for i, chain in enumerate(chains[:10], 1):
                lines.append(f"Chain {i} ({len(chain)} levels):")
                lines.append("  " + " -> ".join(chain))
                lines.append("")
        else:
            lines.append("No excessively long chains found ✓")
        lines.append("")

        # High coupling modules
        lines.append("## HIGH COUPLING ANALYSIS")
        lines.append("-" * 80)
        coupling_scores = []
        for module in self.dependency_graph:
            outgoing = len(self.dependency_graph.get(module, set()))
            incoming = len(self.reverse_dependency_graph.get(module, set()))
            coupling = outgoing + incoming
            if coupling > 10:
                coupling_scores.append((module, outgoing, incoming, coupling))

        coupling_scores.sort(key=lambda x: x[3], reverse=True)
        lines.append("Top modules by total coupling (imports + imported by):\n")
        for module, out_deg, in_deg, total in coupling_scores[:15]:
            lines.append(f"{total:3d} total | {out_deg:2d} out | {in_deg:2d} in  | {module}")
        lines.append("")

        # Recommendations
        lines.append("## REFACTORING RECOMMENDATIONS")
        lines.append("-" * 80)
        lines.append("")

        if cycles:
            lines.append("1. CRITICAL: Resolve circular dependencies")
            lines.append("   - Circular imports can cause initialization issues")
            lines.append("   - Consider dependency injection or interface extraction")
            lines.append("")

        if excessive:
            lines.append("2. REDUCE MODULE COMPLEXITY")
            lines.append(f"   - {len(excessive)} modules have >20 imports")
            lines.append("   - Consider splitting large modules")
            lines.append("   - Extract interfaces or create facades")
            lines.append("")

        if coupling_scores:
            lines.append("3. DECOUPLE HIGH-COUPLING MODULES")
            top_coupled = coupling_scores[0] if coupling_scores else None
            if top_coupled:
                lines.append(f"   - '{top_coupled[0]}' has coupling score of {top_coupled[3]}")
                lines.append("   - Consider introducing abstractions or mediators")
            lines.append("")

        if mixed_style:
            lines.append("4. STANDARDIZE IMPORT STYLE")
            lines.append(f"   - {len(mixed_style)} modules mix relative/absolute imports")
            lines.append("   - Establish and enforce a consistent import convention")
            lines.append("")

        lines.append("## DEPENDENCY HOTSPOTS (Most Critical Modules)")
        lines.append("-" * 80)
        lines.append("These modules are imported most frequently and should be:")
        lines.append("- Well-tested and stable")
        lines.append("- Have clear, minimal interfaces")
        lines.append("- Documented thoroughly")
        lines.append("")

        for module, count in self.import_counts.most_common(5):
            lines.append(f"  • {module} ({count} imports)")
            # Show coupling info
            outgoing = len(self.dependency_graph.get(module, set()))
            incoming = len(self.reverse_dependency_graph.get(module, set()))
            lines.append(f"    Depends on: {outgoing} modules | Imported by: {incoming} modules")

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    root_dir = "/Users/bjh/cell_OS"
    analyzer = ImportAnalyzer(root_dir)
    analyzer.analyze_all()
    report = analyzer.generate_report()

    # Write report
    report_path = Path(root_dir) / "import_analysis_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
