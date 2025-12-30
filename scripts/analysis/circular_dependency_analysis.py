#!/usr/bin/env python3
"""
Detailed circular dependency analysis with resolution strategies.
"""
import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class CircularDependencyAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.src_dir = self.root_dir / "src" / "cell_os"
        self.dependency_graph = defaultdict(set)
        self.import_details = defaultdict(list)

    def parse_imports(self, file_path: Path) -> List[Tuple[str, str, int]]:
        """Parse imports and return (source_module, target_module, line_number)."""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('cell_os'):
                            imports.append((alias.name, node.lineno))

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    if module.startswith('cell_os') or (node.level > 0):
                        imports.append((module, node.lineno))

        except Exception as e:
            pass

        return imports

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
            return str(file_path)

    def build_graph(self):
        """Build dependency graph."""
        py_files = list(self.src_dir.rglob("*.py"))

        for file_path in py_files:
            source_module = self.get_module_name(file_path)
            imports = self.parse_imports(file_path)

            for target_module, line_no in imports:
                if target_module.startswith('cell_os'):
                    self.dependency_graph[source_module].add(target_module)
                    self.import_details[source_module].append({
                        'target': target_module,
                        'line': line_no,
                        'file': str(file_path)
                    })

    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the dependency graph."""
        cycles = []
        visited = set()
        rec_stack = []

        def dfs(node: str):
            if node in rec_stack:
                cycle_start = rec_stack.index(node)
                cycle = rec_stack[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.append(node)

            for neighbor in self.dependency_graph.get(node, []):
                dfs(neighbor)

            rec_stack.pop()

        for node in self.dependency_graph:
            if node not in visited:
                dfs(node)

        # Deduplicate
        unique_cycles = []
        seen_cycles = set()
        for cycle in cycles:
            min_idx = cycle.index(min(cycle))
            normalized = tuple(cycle[min_idx:-1])
            if normalized not in seen_cycles:
                seen_cycles.add(normalized)
                unique_cycles.append(list(normalized) + [normalized[0]])

        return unique_cycles

    def analyze_cycle(self, cycle: List[str]) -> Dict:
        """Analyze a specific cycle and suggest resolution."""
        analysis = {
            'cycle': cycle,
            'length': len(cycle) - 1,
            'edges': []
        }

        # Analyze each edge in the cycle
        for i in range(len(cycle) - 1):
            source = cycle[i]
            target = cycle[i + 1]

            # Find what's imported
            imports = [imp for imp in self.import_details.get(source, [])
                      if imp['target'] == target or target.startswith(imp['target'])]

            analysis['edges'].append({
                'from': source,
                'to': target,
                'imports': imports
            })

        # Suggest resolution strategy
        analysis['resolution_strategy'] = self.suggest_resolution(cycle)

        return analysis

    def suggest_resolution(self, cycle: List[str]) -> Dict:
        """Suggest strategies to break the cycle."""
        strategies = []

        if len(cycle) == 3:  # Two modules (A -> B -> A)
            strategies.append({
                'name': 'Extract Common Interface',
                'description': 'Create a third module with shared interfaces/types',
                'difficulty': 'Medium',
                'steps': [
                    '1. Identify shared types/interfaces between the two modules',
                    '2. Create a new module (e.g., interfaces.py or types.py)',
                    '3. Move shared definitions to the new module',
                    '4. Both modules import from the new module'
                ]
            })

            strategies.append({
                'name': 'Use TYPE_CHECKING',
                'description': 'Use TYPE_CHECKING for type hints only',
                'difficulty': 'Easy',
                'steps': [
                    '1. Identify which imports are only for type hints',
                    '2. Wrap them in: if TYPE_CHECKING:',
                    '3. Use string literals for forward references',
                    '4. Import from __future__ import annotations (Python 3.10+)'
                ]
            })

            strategies.append({
                'name': 'Dependency Injection',
                'description': 'Pass dependencies as parameters instead of importing',
                'difficulty': 'Medium',
                'steps': [
                    '1. Identify which module is more "core"',
                    '2. Remove import from the other module',
                    '3. Pass the dependency via constructor/function parameters',
                    '4. Update call sites to inject the dependency'
                ]
            })

        else:  # Longer cycle
            strategies.append({
                'name': 'Identify and Break Weakest Link',
                'description': 'Find the edge with fewest imports and break it',
                'difficulty': 'Medium',
                'steps': [
                    '1. Count imports on each edge of the cycle',
                    '2. Choose the edge with the fewest/simplest imports',
                    '3. Apply one of the simple strategies to that edge',
                    '4. Consider if the long chain indicates poor architecture'
                ]
            })

            strategies.append({
                'name': 'Architectural Refactoring',
                'description': 'Long cycles often indicate architectural issues',
                'difficulty': 'Hard',
                'steps': [
                    '1. Analyze if these modules should be in different layers',
                    '2. Consider creating a clear dependency hierarchy',
                    '3. Use interfaces/abstract base classes',
                    '4. Apply dependency inversion principle',
                    '5. May require significant refactoring'
                ]
            })

        return {
            'recommended': strategies[0] if strategies else None,
            'alternatives': strategies[1:] if len(strategies) > 1 else [],
            'all_strategies': strategies
        }

    def generate_detailed_report(self) -> str:
        """Generate detailed analysis of circular dependencies."""
        lines = []
        lines.append("=" * 80)
        lines.append("DETAILED CIRCULAR DEPENDENCY ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        cycles = self.find_cycles()

        if not cycles:
            lines.append("No circular dependencies found!")
            return "\n".join(lines)

        lines.append(f"Found {len(cycles)} circular dependency cycles")
        lines.append("")

        for i, cycle in enumerate(cycles, 1):
            lines.append("=" * 80)
            lines.append(f"CYCLE #{i}: {len(cycle) - 1}-node cycle")
            lines.append("=" * 80)
            lines.append("")

            # Show the cycle
            lines.append("Cycle path:")
            for j, module in enumerate(cycle):
                if j < len(cycle) - 1:
                    lines.append(f"  [{j+1}] {module}")
                    lines.append(f"      ↓ imports")
                else:
                    lines.append(f"  [{j+1}] {module} (completes cycle)")
            lines.append("")

            # Detailed analysis
            analysis = self.analyze_cycle(cycle)

            # Show what's imported on each edge
            lines.append("Import details:")
            for edge in analysis['edges']:
                lines.append(f"\n  {edge['from']}")
                lines.append(f"    → imports from: {edge['to']}")
                if edge['imports']:
                    lines.append(f"    Import locations:")
                    for imp in edge['imports'][:3]:  # Show first 3
                        lines.append(f"      - Line {imp['line']} in {Path(imp['file']).name}")
                    if len(edge['imports']) > 3:
                        lines.append(f"      ... and {len(edge['imports']) - 3} more")
                else:
                    lines.append(f"    (indirect dependency)")
            lines.append("")

            # Resolution strategies
            resolution = analysis['resolution_strategy']
            lines.append("RECOMMENDED RESOLUTION:")
            lines.append("-" * 80)

            if resolution['recommended']:
                strat = resolution['recommended']
                lines.append(f"Strategy: {strat['name']}")
                lines.append(f"Difficulty: {strat['difficulty']}")
                lines.append(f"Description: {strat['description']}")
                lines.append("")
                lines.append("Steps:")
                for step in strat['steps']:
                    lines.append(f"  {step}")
                lines.append("")

            if resolution['alternatives']:
                lines.append("ALTERNATIVE STRATEGIES:")
                lines.append("-" * 80)
                for alt in resolution['alternatives']:
                    lines.append(f"\n{alt['name']} (Difficulty: {alt['difficulty']})")
                    lines.append(f"  {alt['description']}")
                lines.append("")

            lines.append("")

        # Summary recommendations
        lines.append("=" * 80)
        lines.append("OVERALL RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("Priority Order:")
        lines.append("")

        # Prioritize by cycle length (shorter = easier to fix)
        cycle_priorities = sorted(enumerate(cycles, 1), key=lambda x: len(x[1]))

        for priority, (cycle_num, cycle) in enumerate(cycle_priorities, 1):
            lines.append(f"{priority}. Fix Cycle #{cycle_num} ({len(cycle)-1} nodes)")
            if len(cycle) == 3:
                lines.append("   → Quick win: Use TYPE_CHECKING or extract interface")
            else:
                lines.append("   → Requires architectural review")
            lines.append("")

        lines.append("General Guidelines:")
        lines.append("  • Always prefer TYPE_CHECKING for type-only imports")
        lines.append("  • Consider if circular deps indicate wrong module boundaries")
        lines.append("  • Use dependency injection for runtime dependencies")
        lines.append("  • Create interface modules for shared types")
        lines.append("  • Apply dependency inversion principle")
        lines.append("")

        return "\n".join(lines)


def main():
    root_dir = "/Users/bjh/cell_OS"
    analyzer = CircularDependencyAnalyzer(root_dir)

    print("Building dependency graph...")
    analyzer.build_graph()

    print("Analyzing circular dependencies...")
    report = analyzer.generate_detailed_report()

    report_path = Path(root_dir) / "circular_dependency_detailed.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
