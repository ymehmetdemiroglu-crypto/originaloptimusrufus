#!/usr/bin/env python3
"""Standalone email drafter — no Claude Code required.

Usage:
    python draft_emails.py              # draft up to 100 brands
    python draft_emails.py --limit=20  # draft up to 20 brands
"""
import os
import subprocess
import sys

limit = next(
    (a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--limit=")),
    "100",
)
script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acquisition_tool", "main.py")
subprocess.run([sys.executable, script, "draft-emails", f"--limit={limit}"], check=True)
