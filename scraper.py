#!/usr/bin/env python3

import os
import logging
import sys
import json
import requests
import base64
from pathlib import Path

GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    logging.warning("No GITHUB_TOKEN provided. You may be rate limited more often and will not be able to access private repositories.")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

SOURCES_FILE = "sources.json"
OUT_DIR = Path("Maps")

def read_sources(path):
    p = Path(path)
    if not p.exists():
        logging.critical(f"{path} not found.")
        sys.exit(1)

    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        logging.critical(f"Malformed JSON in {path}: {e}")
        sys.exit(1)

    sources = data.get("sources")

    if not isinstance(sources, list):
        logging.critical(f'"sources" must be a list in {path}')
        sys.exit(1)

    if not sources:
        logging.critical(f"No GitHub repositories listed in {path}")
        sys.exit(1)

    return sources

def get_default_branch(repo):
    r = requests.get(f"{GITHUB_API}/repos/{repo}", headers=HEADERS)
    r.raise_for_status()
    return r.json().get("default_branch", "main")

def get_tree(repo, branch):
    # Resolve branch to commit SHA
    br = requests.get(f"{GITHUB_API}/repos/{repo}/branches/{branch}", headers=HEADERS)
    br.raise_for_status()
    sha = br.json()["commit"]["sha"]

    # Fetch full tree
    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/trees/{sha}",
        headers=HEADERS,
        params={"recursive": "1"}
    )
    r.raise_for_status()
    return r.json()["tree"]

def download_raw(repo, branch, path, dest, sha=None):
    url = f"{RAW_BASE}/{repo}/{branch}/{path}"
    r = requests.get(url, headers=HEADERS, stream=True)

    # Fallback for private repos
    if r.status_code == 404 and HEADERS and sha:
        b = requests.get(f"{GITHUB_API}/repos/{repo}/git/blobs/{sha}", headers=HEADERS)
        b.raise_for_status()
        content = b.json().get("content", "")
        data = base64.b64decode(content or "")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return

    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

def handle_github_repo(repo, branch_override=None):
    try:
        branch = branch_override or get_default_branch(repo)
        tree = get_tree(repo, branch)
    except requests.HTTPError as e:
        logging.error(f"Skipping {repo}: {e}")
        return

    # Look for map.png files
    for item in tree:
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")
        if not path.lower().endswith("map.png"):
            continue

        p = Path(path)
        folder = p.parent
        folders = list(folder.parts)

        # Base map folder
        if len(folders) >= 2:
            base = folders[1]
        else:
            base = folders[-1]

        # Variant exists only if depth is 3
        if len(folders) == 3:
            keep_parts = [base, folders[2]]
        else:
            keep_parts = [base]

        dest_dir = OUT_DIR.joinpath(*keep_parts)
        dest_file = dest_dir / "map.png"
        sha_file = dest_dir / ".map_sha"

        remote_sha = item.get("sha")
        local_sha = sha_file.read_text(encoding="utf-8").strip() if sha_file.exists() else None

        if local_sha == remote_sha and dest_file.exists():
            logging.debug(f"{path} -> {dest_file} is up to date, skipping.")
            continue

        print(f"Downloading: {repo} -> {path} -> {dest_file}")
        try:
            download_raw(repo, branch, path, dest_file, sha=remote_sha)
            sha_file.parent.mkdir(parents=True, exist_ok=True)
            sha_file.write_text(remote_sha or "", encoding="utf-8")
        except requests.HTTPError as e:
            logging.error(f"Failed to download {repo}:{path}: {e}")

def handle_source(source):
    repo = source.get("repository", "")
    branch = source.get("branch")

    if repo:
        handle_github_repo(repo, branch_override=branch)
    else:
        logging.warning(f"Skipping inaccessible or unsupported source: {repo}")

def main():
    sources = read_sources(SOURCES_FILE)
    for src in sources:
        print("Processing source:", src.get("repository"))
        handle_source(src)
    print("Finished processing map images.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting now.")
        sys.exit(0)
