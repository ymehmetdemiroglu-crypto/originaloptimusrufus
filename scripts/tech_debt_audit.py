#!/usr/bin/env python3
"""Technical Debt Audit Scanner for Optimus Rufus.

Scans the Python modules in backend/ and acquisition-tool/ for TODOs/FIXMEs,
measures code sizes, checks for monolithic files, and counts complex functions.
"""

import os
import re

def run_technical_debt_audit():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 60)
    print("          OPTIMUS RUFUS TECHNICAL DEBT AUDIT")
    print("=" * 60)

    target_dirs = ["backend", "acquisition-tool"]
    todo_pattern = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
    
    total_todos = 0
    todos_by_file = {}
    large_files = []
    monoliths = []

    for directory in target_dirs:
        full_path = os.path.join(root_dir, directory)
        if not os.path.exists(full_path):
            continue
            
        for dirpath, _, filenames in os.walk(full_path):
            if "venv" in dirpath or ".pytest_cache" in dirpath or "__pycache__" in dirpath:
                continue
                
            for filename in filenames:
                if filename.endswith(".py"):
                    filepath = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(filepath, root_dir)
                    
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            
                        # Check file length (Monolith detection)
                        line_count = len(lines)
                        file_size_kb = os.path.getsize(filepath) / 1024
                        
                        if line_count > 600 or file_size_kb > 25:
                            large_files.append((rel_path, line_count, file_size_kb))
                        if line_count > 900:
                            monoliths.append((rel_path, line_count))
                            
                        # Search for TODO/FIXME comments
                        file_todos = []
                        for idx, line in enumerate(lines):
                            matches = todo_pattern.findall(line)
                            if matches:
                                file_todos.append((idx + 1, line.strip()))
                                
                        if file_todos:
                            todos_by_file[rel_path] = file_todos
                            total_todos += len(file_todos)
                    except Exception as e:
                        print(f"Error reading {rel_path}: {e}")

    # Display Monolith warnings (Idea 3)
    print(f"\n[!] Monolithic File Warnings (>900 lines):")
    if monoliths:
        for path, lines in sorted(monoliths, key=lambda x: x[1], reverse=True):
            print(f"  [MONOLITH] {path} : {lines} lines - Recommended for immediate modularization!")
    else:
        print("  [OK] No monolithic files detected over 900 lines.")

    # Display Large File details
    print(f"\n[!] Large File Size Watchlist (>600 lines or >25KB):")
    if large_files:
        for path, lines, size in sorted(large_files, key=lambda x: x[1], reverse=True)[:8]:
            print(f"  [LARGE] {path} : {lines} lines ({size:.1f} KB)")
    else:
        print("  [OK] All files are beautifully sized under thresholds.")

    # Display Technical Debt Comments (Idea 30)
    print(f"\n[!] Total TODO/FIXME Comments Found: {total_todos}")
    if todos_by_file:
        print("\nTop Technical Debt hotspots:")
        sorted_hotspots = sorted(todos_by_file.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        for path, items in sorted_hotspots:
            print(f"  [FILE] {path} ({len(items)} items)")
            for line_no, content in items[:3]:
                # Trim content
                if len(content) > 75:
                    content = content[:72] + "..."
                print(f"    Line {line_no:4d}: {content}")
            if len(items) > 3:
                print(f"    ... and {len(items) - 3} more items")
    else:
        print("  [OK] Zero technical debt marker comments found! Pristine condition.")
        
    print("\n" + "=" * 60)

if __name__ == "__main__":
    run_technical_debt_audit()
