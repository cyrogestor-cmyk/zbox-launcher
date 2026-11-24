#!/usr/bin/env python3
"""Helper invoked by .github/workflows/sync-upstream.yml when merging upstream/main into zbox.

If git merge hits a conflict on src-tauri/tauri.conf.json (common because upstream bumps "version"
right next to ZBOX's productName/identifier), this script keeps ZBOX's tauri.conf.json and copies
only the new "version" from upstream. Any unexpected code conflict fails cleanly so nothing broken
is ever pushed.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def main() -> int:
    merge = run("git", "merge", "FETCH_HEAD", "--no-edit", check=False)
    if merge.returncode == 0:
        print("Clean merge from upstream/main.")
        return 0

    unmerged = [
        line.strip()
        for line in run("git", "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        if line.strip()
    ]
    print("Unmerged files:", unmerged)

    # Files where ZBOX owns the content and upstream only bumps version or branding assets.
    zbox_owned_binaries = {
        "ui/img/mark.svg",
        "ui/img/wordmark.svg",
        "ui/img/wordmark-dark.svg",
        "ui/img/logo.svg",
        "ui/splash.html",
        "src-tauri/installer/header.bmp",
        "src-tauri/installer/sidebar.bmp",
    }

    unresolved = []
    for path in unmerged:
        if path == "src-tauri/tauri.conf.json":
            ours = json.loads(run("git", "show", ":2:src-tauri/tauri.conf.json").stdout)
            theirs = json.loads(run("git", "show", ":3:src-tauri/tauri.conf.json").stdout)
            ours["version"] = theirs["version"]
            with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as f:
                json.dump(ours, f, indent=2)
                f.write("\n")
            run("git", "add", path)
            print(f"Auto-resolved {path}: kept ZBOX config with upstream version {ours['version']}.")
        elif path in zbox_owned_binaries or path.startswith("src-tauri/icons/"):
            run("git", "checkout", "--ours", "--", path)
            run("git", "add", path)
            print(f"Auto-resolved {path}: kept ZBOX asset.")
        else:
            unresolved.append(path)

    if unresolved:
        print("Manual resolution required for:", unresolved, file=sys.stderr)
        run("git", "merge", "--abort", check=False)
        return 1

    run("git", "commit", "--no-edit")
    print("Resolved merge committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
