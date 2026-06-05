#!/usr/bin/env python3
"""Context-efficient manifest of an Obsidian-vault project.

Lists root files of interest and session files (newest first) WITHOUT ever
printing file bodies. Only the head of each session file (~40 lines) is read,
solely to extract a title.
"""
import json
import os
import sys


def workspace_root():
    return os.environ.get("WORKSPACE_ROOT", "/mnt/filesystem-a6/cc_workspace_mats")


def vault_path():
    return os.environ.get("VAULT_PATH", f"{workspace_root()}/projects/dohun_vault")


def count_lines_and_bytes(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    lines = 0
    try:
        with open(path, "rb") as fh:
            for _ in fh:
                lines += 1
    except OSError:
        lines = 0
    return lines, size


def extract_title(path):
    """First markdown H1 (# ...) or frontmatter title:. Reads only the head."""
    h1 = None
    fm_title = None
    in_frontmatter = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for i, raw in enumerate(fh):
                if i >= 40:
                    break
                line = raw.rstrip("\n")
                stripped = line.strip()
                if i == 0 and stripped == "---":
                    in_frontmatter = True
                    continue
                if in_frontmatter:
                    if stripped == "---":
                        in_frontmatter = False
                        continue
                    if fm_title is None and stripped.lower().startswith("title:"):
                        val = stripped.split(":", 1)[1].strip().strip("'\"")
                        if val:
                            fm_title = val
                    continue
                if h1 is None and stripped.startswith("# "):
                    h1 = stripped[2:].strip()
                    break
    except OSError:
        pass
    if h1:
        return h1
    if fm_title:
        return fm_title
    return ""


def available_projects(vault):
    """Subdirs with a STATE.md; else all non-hidden subdirs."""
    with_state = []
    all_subdirs = []
    try:
        for name in sorted(os.listdir(vault)):
            if name.startswith("."):
                continue
            full = os.path.join(vault, name)
            if not os.path.isdir(full):
                continue
            all_subdirs.append(name)
            if os.path.isfile(os.path.join(full, "STATE.md")):
                with_state.append(name)
    except OSError:
        pass
    return with_state if with_state else all_subdirs


def gather(vault, project):
    proj_dir = os.path.join(vault, project)
    root_files = []
    for name in ("STATE.md", "README.md", "AGENTS.md"):
        fpath = os.path.join(proj_dir, name)
        if os.path.isfile(fpath):
            lines, size = count_lines_and_bytes(fpath)
            root_files.append({"name": name, "lines": lines, "bytes": size})

    sessions = []
    sess_dir = os.path.join(proj_dir, "sessions")
    if os.path.isdir(sess_dir):
        entries = []
        try:
            for name in os.listdir(sess_dir):
                if name.endswith(".md") and os.path.isfile(os.path.join(sess_dir, name)):
                    entries.append(name)
        except OSError:
            entries = []
        # Sort newest first by filename desc (timestamp-prefixed); fall back to mtime.
        def sort_key(n):
            try:
                mt = os.path.getmtime(os.path.join(sess_dir, n))
            except OSError:
                mt = 0
            return (n, mt)

        entries.sort(key=sort_key, reverse=True)
        for name in entries:
            fpath = os.path.join(sess_dir, name)
            lines, size = count_lines_and_bytes(fpath)
            title = extract_title(fpath)
            sessions.append(
                {"name": name, "title": title, "lines": lines, "bytes": size}
            )
    return root_files, sessions


def main(argv):
    args = [a for a in argv[1:]]
    as_json = "--json" in args
    positional = [a for a in args if a != "--json"]
    if len(positional) != 1:
        sys.stderr.write("usage: context_manifest.py <project> [--json]\n")
        return 2
    project = positional[0]
    vault = vault_path()
    proj_dir = os.path.join(vault, project)

    if not os.path.isdir(proj_dir):
        avail = available_projects(vault)
        if as_json:
            print(json.dumps({"status": "missing", "project": project, "available": avail}))
        else:
            print(f"MISSING: {project}")
            print("available: " + ", ".join(avail))
        return 2

    root_files, sessions = gather(vault, project)

    if as_json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project": project,
                    "root_files": root_files,
                    "sessions": sessions,
                }
            )
        )
        return 0

    # Text mode: compact, aligned.
    print(f"PROJECT {project} ({len(sessions)} sessions)")
    if root_files:
        name_w = max(len(f["name"]) for f in root_files)
        for f in root_files:
            print(f"  {f['name']:<{name_w}}  {f['lines']:>5} lines  {f['bytes']:>8} bytes")
    print("sessions (newest first):")
    if sessions:
        name_w = max(len(s["name"]) for s in sessions)
        for s in sessions:
            title = s["title"] or "(untitled)"
            print(
                f"  {s['name']:<{name_w}}  {s['lines']:>5} lines  {s['bytes']:>8} bytes  {title}"
            )
    else:
        print("  (none)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
