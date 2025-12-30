#!/usr/bin/env python3
"""
Find potentially unused imports in Python files.
"""
import ast
from pathlib import Path
from typing import Dict, List, Set
import re


class UnusedImportAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.src_dir = self.root_dir / "src" / "cell_os"
        self.results = []

    def extract_names(self, node):
        """Extract all Name nodes from an AST."""
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                names.add(child.id)
            elif isinstance(child, ast.Attribute):
                # Get the base name (e.g., 'np' from 'np.array')
                while isinstance(child, ast.Attribute):
                    child = child.value
                if isinstance(child, ast.Name):
                    names.add(child.id)
        return names

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single file for unused imports."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            return None

        # Extract imports
        imports = {}
        import_nodes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_nodes.append(node)
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split('.')[0]
                    imports[name] = {
                        'type': 'import',
                        'module': alias.name,
                        'line': node.lineno
                    }

            elif isinstance(node, ast.ImportFrom):
                import_nodes.append(node)
                for alias in node.names:
                    if alias.name == '*':
                        # Can't analyze star imports
                        continue
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = {
                        'type': 'from',
                        'module': node.module or '',
                        'line': node.lineno
                    }

        # Build a tree without imports
        body_without_imports = [node for node in tree.body
                               if not isinstance(node, (ast.Import, ast.ImportFrom))]

        # Extract all names used in the code
        used_names = set()
        for node in body_without_imports:
            used_names.update(self.extract_names(node))

        # Check for TYPE_CHECKING pattern
        has_type_checking = 'TYPE_CHECKING' in content

        # Find unused imports
        unused = []
        for name, info in imports.items():
            # Skip special cases
            if name in ['TYPE_CHECKING', 'annotations', '__future__']:
                continue

            # Check if used
            if name not in used_names:
                # Additional check: might be used in string type hints
                if not re.search(rf'\b{re.escape(name)}\b', content.replace(f'import {name}', '')):
                    unused.append({
                        'name': name,
                        'line': info['line'],
                        'module': info['module'],
                        'type': info['type']
                    })

        if unused:
            return {
                'file': str(file_path.relative_to(self.src_dir)),
                'unused_count': len(unused),
                'unused': unused,
                'total_imports': len(imports)
            }

        return None

    def analyze_all(self):
        """Analyze all Python files."""
        py_files = list(self.src_dir.rglob("*.py"))

        for file_path in py_files:
            result = self.analyze_file(file_path)
            if result:
                self.results.append(result)

    def generate_report(self) -> str:
        """Generate report of unused imports."""
        lines = []
        lines.append("=" * 80)
        lines.append("POTENTIALLY UNUSED IMPORTS ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        if not self.results:
            lines.append("No obvious unused imports found!")
            lines.append("")
            lines.append("Note: This analysis may have false positives/negatives.")
            lines.append("Manual review is recommended.")
            return "\n".join(lines)

        # Sort by number of unused imports
        self.results.sort(key=lambda x: x['unused_count'], reverse=True)

        lines.append(f"Found {len(self.results)} files with potentially unused imports")
        lines.append("")

        # Summary stats
        total_unused = sum(r['unused_count'] for r in self.results)
        lines.append(f"Total potentially unused imports: {total_unused}")
        lines.append("")

        # Top offenders
        lines.append("## TOP 20 FILES WITH MOST UNUSED IMPORTS")
        lines.append("-" * 80)
        for result in self.results[:20]:
            lines.append(f"\n{result['file']}")
            lines.append(f"  {result['unused_count']} unused out of {result['total_imports']} total imports")
            lines.append("  Unused imports:")
            for imp in result['unused'][:10]:  # Show first 10
                lines.append(f"    Line {imp['line']:3d}: {imp['name']} (from {imp['module']})")
            if len(result['unused']) > 10:
                lines.append(f"    ... and {len(result['unused']) - 10} more")

        lines.append("")
        lines.append("=" * 80)
        lines.append("NOTE: This is a heuristic analysis and may include false positives.")
        lines.append("Examples of false positives:")
        lines.append("  - Imports used only in type hints or string annotations")
        lines.append("  - Imports used via getattr() or eval()")
        lines.append("  - Imports that define module-level behavior on import")
        lines.append("  - Imports required for side effects")
        lines.append("Manual review recommended before removing any imports.")
        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    root_dir = "/Users/bjh/cell_OS"
    analyzer = UnusedImportAnalyzer(root_dir)
    print("Analyzing unused imports...")
    analyzer.analyze_all()
    report = analyzer.generate_report()

    report_path = Path(root_dir) / "unused_imports_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
