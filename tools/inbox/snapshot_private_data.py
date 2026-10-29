#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a local, private snapshot of inbox metadata and ASR records."""
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime

INBOX = os.path.dirname(os.path.abspath(__file__))
EXTRA = os.path.join(INBOX, "inbox_extra.jsonl")
STATE = os.path.join(INBOX, "inbox_state.jsonl")
RECORDS = os.path.join(INBOX, "asr", "records")
BACKUPS = os.path.join(INBOX, "private_backups")


def collect_files():
    files = {}
    if os.path.isfile(EXTRA) and not os.path.islink(EXTRA):
        os.chmod(EXTRA, 0o600)
        rel = os.path.relpath(EXTRA, INBOX).replace(os.sep, "/")
        with open(EXTRA, "rb") as f:
            files[rel] = f.read()
    if os.path.isfile(STATE) and not os.path.islink(STATE):
        os.chmod(STATE, 0o600)
        with open(STATE, "rb") as f:
            files["inbox_state.jsonl"] = f.read()
    if os.path.isdir(RECORDS) and not os.path.islink(RECORDS):
        os.chmod(RECORDS, 0o700)
        for root, dirs, names in os.walk(RECORDS, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
            os.chmod(root, 0o700)
            for name in sorted(names):
                path = os.path.join(root, name)
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                os.chmod(path, 0o600)
                rel = os.path.relpath(path, INBOX).replace(os.sep, "/")
                with open(path, "rb") as f:
                    files[rel] = f.read()
    return files


def main():
    files = collect_files()
    if not files:
        print("没有可快照的收件箱私有数据")
        return

    digest = hashlib.sha256()
    entries = []
    for rel, content in sorted(files.items()):
        rel_bytes = rel.encode("utf-8")
        file_hash = hashlib.sha256(content).hexdigest()
        digest.update(len(rel_bytes).to_bytes(4, "big"))
        digest.update(rel_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        entries.append({"path": rel, "sha256": file_hash, "size": len(content)})
    snapshot_hash = digest.hexdigest()

    os.makedirs(BACKUPS, mode=0o700, exist_ok=True)
    if os.path.islink(BACKUPS):
        raise RuntimeError("私有快照目录不能是软链")
    os.chmod(BACKUPS, 0o700)
    if any(name.startswith("inbox-data-") and name.endswith(f"-{snapshot_hash[:16]}.zip")
           for name in os.listdir(BACKUPS)):
        print(f"私有数据未变化，已有快照（SHA-256 {snapshot_hash[:16]}）")
        return

    now = datetime.now().astimezone()
    created = now.isoformat(timespec="seconds")
    stamp = now.strftime("%Y%m%d-%H%M%S")
    name = f"inbox-data-{stamp}-{snapshot_hash[:16]}.zip"
    target = os.path.join(BACKUPS, name)
    manifest = {
        "created_at": created,
        "sha256": snapshot_hash,
        "files": entries,
    }

    fd, temporary = tempfile.mkstemp(dir=BACKUPS, prefix=".snapshot-", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for rel, content in sorted(files.items()):
                archive.writestr(rel, content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"已创建本机私有数据快照: {name}（{len(files)} 个文件）")


if __name__ == "__main__":
    main()
