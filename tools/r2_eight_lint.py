# Simple Python linter (stdlib ast/compile): syntax errors, unused imports/variables, undefined names, long lines, missing docstrings.
import ast
import builtins

MAX_LINE = 99


def lint(code_str, max_line=MAX_LINE):
    """Return a sorted list of (line, code, message) issues for code_str. Never executes the code."""
    issues = []
    for i, line in enumerate(code_str.splitlines(), 1):
        if len(line) > max_line:
            issues.append((i, "E501", f"line too long ({len(line)} > {max_line})"))
    try:
        compile(code_str, "<code>", "exec", dont_inherit=True)
        tree = ast.parse(code_str)
    except SyntaxError as e:
        issues.append((e.lineno or 0, "E999", f"SyntaxError: {e.msg}"))
        return sorted(issues)

    if not ast.get_docstring(tree):
        issues.append((1, "D100", "missing module docstring"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not ast.get_docstring(node) and not node.name.startswith("_"):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                issues.append((node.lineno, "D101", f"missing docstring in {kind} '{node.name}'"))

    # Imports
    imported = {}
    star = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    star = True
                else:
                    imported[a.asname or a.name] = node.lineno

    # Every name defined anywhere, and every name loaded
    defined = set(dir(builtins)) | set(imported) | {"__name__", "__file__", "__doc__"}
    loaded = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                defined.add(node.id)
            else:
                loaded.setdefault(node.id, node.lineno)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
        elif hasattr(ast, "MatchAs") and isinstance(node, getattr(ast, "MatchAs")) and node.name:
            defined.add(node.name)
    used = set(loaded)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)
    exported = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            try:
                exported = set(ast.literal_eval(node.value))
            except Exception:
                pass

    for name, ln in imported.items():
        if name not in used and name not in exported:
            issues.append((ln, "F401", f"'{name}' imported but unused"))
    if not star:
        for name, ln in loaded.items():
            if name not in defined:
                issues.append((ln, "F821", f"undefined name '{name}'"))

    # Unused local variables per function
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stores, loads, declared = {}, set(), set()
        for node in ast.walk(fn):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                declared.update(node.names)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    stores.setdefault(node.id, node.lineno)
                else:
                    loads.add(node.id)
        for name, ln in stores.items():
            if name not in loads and name not in declared and not name.startswith("_"):
                issues.append((ln, "F841", f"local variable '{name}' assigned but never used"))
    return sorted(set(issues))


def report(code_str):
    """Print lint results in a readable format."""
    issues = lint(code_str)
    if not issues:
        print("No issues found.")
    for ln, code, msg in issues:
        print(f"line {ln}: {code} {msg}")
    return issues


SAMPLE = '''import os
import sys, json

def greet(name):
    unused = 5
    print("hi " + name + missing_var)
    return json.dumps({"name": name})

class Thing:
    pass

x = "''' + "a" * 110 + '''"
'''

if __name__ == "__main__":
    print("--- sample ---")
    report(SAMPLE)
    print("--- syntax error sample ---")
    report("def f(:\n    pass\n")
    choice = input("\nPaste one line of code to lint (or Enter to skip): ")
    if choice.strip():
        report(choice)
