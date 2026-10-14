"""R0 static import inventory and transitive headless boundary gate (stdlib only)."""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOTS = ('tkinter', '_tkinter', 'PySide6', 'PyQt6', 'PyQt5')
HEADLESS = ('drawtemp.core', 'drawtemp.sdk')


def inventory(root=ROOT):
    graph, eager_graph, dynamic = {}, {}, []
    for package in ('sporebound', 'drawtemp'):
        for path in sorted((root / package).rglob('*.py')):
            relative = path.relative_to(root).with_suffix('')
            parts = list(relative.parts)
            is_package = parts[-1] == '__init__'
            if is_package:
                parts.pop()
            module = '.'.join(parts)
            parent = parts if is_package else parts[:-1]
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            def eager_nodes(node):
                yield node
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    for child in ast.iter_child_nodes(node):
                        yield from eager_nodes(child)
            eager_ids = {id(node) for node in eager_nodes(tree)}
            all_imports, eager = set(), set()
            for node in ast.walk(tree):
                imports = set()
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    prefix = parent[:len(parent) - node.level + 1] if node.level else []
                    base = '.'.join(prefix + ([node.module] if node.module else []))
                    imports.add(base)
                    imports.update(base + '.' + alias.name for alias in node.names)
                elif isinstance(node, ast.Call):
                    name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
                    if name in ('import_module', '__import__'):
                        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                            imports.add(node.args[0].value)
                        else:
                            dynamic.append({'module': module, 'line': node.lineno})
                if id(node) in eager_ids:
                    eager.update(imports)
                all_imports.update(imports)
            graph[module] = sorted(all_imports - {''})
            eager_graph[module] = sorted(eager - {''})

    def dependencies(module, source):
        result = set()
        for target in source[module]:
            # Include package __init__ execution and the longest known submodule.
            parts = target.split('.')
            result.update('.'.join(parts[:i]) for i in range(1, len(parts)+1)
                          if '.'.join(parts[:i]) in graph)
        return result

    direct = {m: sorted({i for i in imports if i.split('.')[0] in UI_ROOTS})
              for m, imports in graph.items()}
    direct = {m: imports for m, imports in direct.items() if imports}
    def paths(source):
        violations = []
        for start in sorted(m for m in graph if m.startswith(HEADLESS)):
            queue, seen = [(start, [start])], set()
            while queue:
                module, path = queue.pop(0)
                if module in seen:
                    continue
                seen.add(module)
                ui = [i for i in source[module] if i.split('.')[0] in UI_ROOTS]
                if ui:
                    violations.append(path + [ui[0]])
                queue.extend((other, path + [other]) for other in sorted(dependencies(module, source)) if other not in seen)
        return violations
    violations = paths(eager_graph)
    return {'schema': 1, 'module_count': len(graph), 'direct_ui_imports': direct,
            'dynamic_imports_to_review': dynamic, 'headless_violations': violations,
            'deferred_ui_paths_to_extract_in_r1': paths(graph), 'imports': graph}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--strict', action='store_true', help='Also reject deferred UI paths')
    args = parser.parse_args()
    report = inventory()
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'imports'}, indent=2))
    blocked = report['headless_violations'] or (args.strict and report['deferred_ui_paths_to_extract_in_r1'])
    return 1 if (args.check or args.strict) and blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
