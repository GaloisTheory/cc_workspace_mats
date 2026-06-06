#!/usr/bin/env python3
"""Allocate a deterministic, unique session markdown path under a project.

Prints the absolute path on stdout. Does NOT create the file (only the parent
directory). The path is guaranteed not to collide with an existing file.
"""
import os
import re
import sys
from datetime import datetime, timezone


def workspace_root():
    return os.environ.get("WORKSPACE_ROOT", "/mnt/filesystem-a6/cc_workspace_mats")


def vault_path():
    return os.environ.get("VAULT_PATH", f"{workspace_root()}/projects/dohun_vault")


def slugify(text):
    text = text.lower()
    # Replace runs of non-alphanumeric with a single hyphen.
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Collapse repeats and strip leading/trailing hyphens.
    text = re.sub(r"-+", "-", text).strip("-")
    text = text[:50].strip("-")
    return text or "session"


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: allocate_session_path.py <project> "<focus>"\n')
        return 2
    project = argv[1]
    focus = argv[2]

    vault = vault_path()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = slugify(focus)

    parent = os.path.join(vault, project, "sessions")
    os.makedirs(parent, exist_ok=True)

    base_name = f"{timestamp}-{slug}"
    candidate = os.path.join(parent, f"{base_name}.md")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(parent, f"{base_name}-{n}.md")
        n += 1

    print(os.path.abspath(candidate))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
