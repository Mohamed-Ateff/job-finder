"""Entry point on the cloud server (Render).

The server's disk is wiped whenever it restarts or wakes from sleep, so the app's data lives in a
private Hugging Face dataset on the same account:
  1. on start, everything saved is downloaded back into the app folder;
  2. every 15 seconds, files the app added, changed or deleted are saved to the dataset;
  3. then the web app is served on the port the host gives ($PORT).
Only data is saved (people, jobs, searches, CVs, settings) - never the code.
"""

import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = os.environ.get("DATA_REPO", "")
TOKEN = os.environ.get("HF_TOKEN", "")
SAVE_EVERY = 15
FOLDERS = ("candidates/", "data/", "runs/", "backups/")
ROOT_FILES = re.compile(r"^(jobs.*|applied_.*|hidden_.*|descriptions_.*|client_checklist)\.json$|^\.env$")


def tracked(rel: str) -> bool:
    if rel.endswith((".tmp", ".pyc", ".lock")) or "__pycache__" in rel or rel.startswith(".cache/"):
        return False
    return rel.startswith(FOLDERS) or ("/" not in rel and bool(ROOT_FILES.match(rel)))


def scan() -> dict[str, tuple[int, int]]:
    found = {}
    for path in ROOT.rglob("*"):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()
            if tracked(rel):
                st = path.stat()
                found[rel] = (st.st_size, st.st_mtime_ns)
    return found


def allow_this_address() -> None:
    """The app only answers on addresses it knows: add this server's own."""
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    hosts = next((ln.split("=", 1)[1].strip() for ln in lines if ln.startswith("APP_ALLOWED_HOSTS=")), "")
    wanted = [h for h in hosts.split(",") if h]
    for extra in (".onrender.com", os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")):
        if extra and extra not in wanted:
            wanted.append(extra)
    lines = [ln for ln in lines if not ln.startswith("APP_ALLOWED_HOSTS=")] + [f"APP_ALLOWED_HOSTS={','.join(wanted)}"]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def keep_saving(api, last: dict) -> None:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete

    while True:
        time.sleep(SAVE_EVERY)
        try:
            now = scan()
            ops = [CommitOperationAdd(path_in_repo=rel, path_or_fileobj=str(ROOT / rel))
                   for rel, stamp in now.items() if last.get(rel) != stamp]
            ops += [CommitOperationDelete(path_in_repo=rel) for rel in last if rel not in now]
            if ops:
                api.create_commit(repo_id=REPO, repo_type="dataset", operations=ops,
                                  commit_message=f"Save {len(ops)} change(s)")
                last = now
        except Exception as exc:  # noqa: BLE001 - a failed save is retried on the next round
            print(f"saving the data failed, retrying: {exc}", flush=True)


def keep_awake() -> None:
    """A free Render server sleeps after 15 minutes without visitors: visit our own public address
    every 5 minutes so it never does, and clients never wait for it to wake."""
    import urllib.request

    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if not host:
        return
    while True:
        time.sleep(300)
        try:
            urllib.request.urlopen(f"https://{host}/api/session", timeout=60).read()
        except Exception as exc:  # noqa: BLE001 - try again next round
            print(f"keep-awake visit failed: {exc}", flush=True)


def main() -> None:
    os.chdir(ROOT)
    threading.Thread(target=keep_awake, daemon=True).start()
    sys.path.insert(0, str(ROOT))
    if REPO and TOKEN:
        from huggingface_hub import HfApi, snapshot_download

        api = HfApi(token=TOKEN)
        print(f"restoring saved data from {REPO}", flush=True)
        snapshot_download(repo_id=REPO, repo_type="dataset", local_dir=ROOT, token=TOKEN)
        allow_this_address()
        threading.Thread(target=keep_saving, args=(api, scan()), daemon=True).start()
    else:
        print("DATA_REPO / HF_TOKEN not set: data will NOT survive a restart", flush=True)
        allow_this_address()

    port = int(os.environ.get("PORT", "10000"))
    os.environ["WEB_HOST"], os.environ["WEB_PORT"] = "0.0.0.0", str(port)
    import uvicorn

    from webapp.server import app

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
