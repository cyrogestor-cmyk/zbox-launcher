#!/usr/bin/env python3
"""Verify ZBOX branding and self-update isolation after an upstream merge.
Exits non-zero if any upstream change reverted ZBOX identity or re-enabled
recomplauncher.com self-updates.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


# 1. tauri.conf.json
conf = json.load(open(os.path.join(ROOT, "src-tauri", "tauri.conf.json"), encoding="utf-8"))
check(conf.get("productName") == "ZBOX", f"productName must be ZBOX, got {conf.get('productName')!r}")
check(conf.get("identifier") == "com.zbox.launcher", f"identifier must be com.zbox.launcher, got {conf.get('identifier')!r}")
check(conf["app"]["windows"][0]["title"] == "ZBOX", "main window title must be ZBOX")

# 2. ui/index.html loads zbox.css
idx = open(os.path.join(ROOT, "ui", "index.html"), encoding="utf-8").read()
check('<link rel="stylesheet" href="zbox.css">' in idx, "ui/index.html must load zbox.css")
check("<title>ZBOX</title>" in idx, "ui/index.html title must be ZBOX")

# 3. ui/i18n.js applies brandText
i18n = open(os.path.join(ROOT, "ui", "i18n.js"), encoding="utf-8").read()
check("brandText" in i18n and "'ZBOX'" in i18n, "ui/i18n.js must keep brandText -> ZBOX")

# 4. Self-update lock in lib.rs and net.rs
lib_rs = open(os.path.join(ROOT, "src-tauri", "src", "lib.rs"), encoding="utf-8").read()
net_rs = open(os.path.join(ROOT, "src-tauri", "src", "net.rs"), encoding="utf-8").read()
check("net::zbox_version_url()" in lib_rs, "lib.rs version_json() must use net::zbox_version_url()")
check('format!("{}/launcher/version.json", catalog::base())' not in lib_rs, "lib.rs must NOT fetch recomplauncher.com/launcher/version.json")
check("elripalda/recomplauncher" in net_rs, "net.rs must explicitly reject upstream repo in zbox_update_repo()")
check("elripalda/recomplauncher" in lib_rs, "lib.rs trusted_update_url() must explicitly reject upstream repo")

# 5. Release workflow injects ZBOX_GITHUB_REPO and builds version.json
rel = open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8").read()
check("ZBOX_GITHUB_REPO" in rel, "release.yml must pass ZBOX_GITHUB_REPO")
check("out/version.json" in rel, "release.yml must generate out/version.json")
check("brand-installer.py" not in rel, "release.yml must not run upstream brand-installer.py")

if errors:
    print("ZBOX BRANDING VERIFICATION FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("ZBOX branding and self-update isolation OK.")
