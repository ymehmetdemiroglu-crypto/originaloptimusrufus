import os
import ast
from collections import defaultdict

class CodeAuditor:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.file_paths = []
        self.definitions = {}  # {name: (file_path, type, node)}
        self.references = defaultdict(list)  # {name: [referencing_file_paths]}
        self.imports = defaultdict(list)  # {file_path: [(imported_name, node)]}
        self.used_imports = defaultdict(set) # {file_path: {referenced_names}}
        self._find_files()
        
    def _find_files(self):
        for root, _, files in os.walk(self.root_dir):
            if "backend-venv" in root or ".pytest_cache" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    self.file_paths.append(os.path.join(root, file))

    def audit(self):
        for path in self.file_paths:
            with open(path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=path)
                except SyntaxError as e:
                    print(f"Syntax error in {path}: {e}")
                    continue
                
                self._parse_node(tree, path)

        # Post-process unused definitions and imports
        unused_defs = []
        for name, (path, def_type, node) in self.definitions.items():
            # Skip FastAPI route handlers (usually have decorators) and standard magic/dunder methods
            if name.startswith("__") and name.endswith("__"):
                continue
            
            # Check if name is referenced in other files or in its own file
            refs = self.references[name]
            # Filter out references in the same file that are just definition nodes
            external_refs = [r for r in refs if r != path]
            
            # Count occurrences in its own file
            is_internally_referenced = False
            if path in refs:
                # We need to make sure it's referenced outside the definition line
                # Simplified check: if it is referenced more than once in its own file
                count = refs.count(path)
                if count > 1:
                    is_internally_referenced = True
            
            if not external_refs and not is_internally_referenced:
                # Make sure it doesn't have a FastAPI routing decorator or typical API route signature
                has_decorator = False
                if hasattr(node, "decorator_list") and node.decorator_list:
                    for dec in node.decorator_list:
                        # FastAPI routing like @app.get, etc.
                        if isinstance(dec, ast.Attribute) and dec.attr in ["get", "post", "put", "delete", "patch", "options"]:
                            has_decorator = True
                        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in ["get", "post", "put", "delete"]:
                            has_decorator = True
                
                if not has_decorator:
                    unused_defs.append((name, path, def_type, node.lineno))

        unused_imports = []
        for path, imps in self.imports.items():
            used = self.used_imports[path]
            for imp, node in imps:
                # Check if imported name is in the set of used names in that file
                # Handle sub-modules/aliases e.g. import foo as bar
                name_to_check = imp
                if "." in imp:
                    name_to_check = imp.split(".")[0]
                if name_to_check not in used:
                    unused_imports.append((imp, path, node.lineno))

        return unused_defs, unused_imports

    def _parse_node(self, tree, path):
        # We walk the AST to extract definitions, references, and imports
        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for name in node.names:
                    alias = name.asname or name.name
                    self.imports[path].append((alias, node))
            elif isinstance(node, ast.ImportFrom):
                for name in node.names:
                    alias = name.asname or name.name
                    self.imports[path].append((alias, node))
            
            # Definitions
            elif isinstance(node, ast.FunctionDef):
                self.definitions[node.name] = (path, "function", node)
            elif isinstance(node, ast.ClassDef):
                self.definitions[node.name] = (path, "class", node)
                
            # References
            elif isinstance(node, ast.Name):
                name = node.id
                if isinstance(node.ctx, ast.Load):
                    self.references[name].append(path)
                    self.used_imports[path].add(name)
            elif isinstance(node, ast.Attribute):
                # e.g., obj.attribute
                self.references[node.attr].append(path)
                self.used_imports[path].add(node.attr)

if __name__ == "__main__":
    # root directory is current working directory (optimus rufus/backend)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
    print(f"Auditing root: {root}")
    auditor = CodeAuditor(root)
    unused_defs, unused_imports = auditor.audit()
    
    print("\n--- UNUSED FUNCTIONS & CLASSES ---")
    for name, path, def_type, line in sorted(unused_defs, key=lambda x: x[1]):
        rel_path = os.path.relpath(path, root)
        print(f"[{def_type.upper()}] '{name}' in {rel_path}:{line}")
        
    print("\n--- UNUSED IMPORTS ---")
    for imp, path, line in sorted(unused_imports, key=lambda x: x[1]):
        rel_path = os.path.relpath(path, root)
        print(f"[IMPORT] '{imp}' in {rel_path}:{line}")
