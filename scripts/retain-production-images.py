#!/usr/bin/env python3
"""Retain the current LAGGENTE application image set and two successful rollbacks."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

IMAGE_KEYS = ("LAGGENTE_API_IMAGE", "LAGGENTE_GATEWAY_IMAGE", "LAGGENTE_BACKUP_IMAGE")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


class RetentionError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RetentionError(message)


class Docker:
    def run(self, *args):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=120)
        require(result.returncode == 0, "Docker command failed: " + " ".join(args[:2]))
        return result.stdout.strip()

    def images(self):
        ids = sorted(set(self.run("image", "ls", "--quiet", "--no-trunc").split()))
        return json.loads(self.run("image", "inspect", *ids)) if ids else []

    def image_id(self, ref):
        images = json.loads(self.run("image", "inspect", ref))
        require(len(images) == 1, "Expected one locally available image")
        return images[0]["Id"]

    def containers(self):
        ids = self.run("container", "ls", "--all", "--quiet").split()
        return json.loads(self.run("container", "inspect", *ids)) if ids else []

    def remove(self, ref):
        # Never force removal, prune the daemon, or remove containers/volumes.
        self.run("image", "rm", "--no-prune", ref)


def release(root, name):
    require(bool(SAFE_ID.fullmatch(name)) and name not in ("current", "previous"), "Invalid release id")
    path = root / "releases" / (name + ".env")
    require(path.is_file() and not path.is_symlink(), "Release metadata missing or symlinked: " + name)
    fields = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key in ("LAGGENTE_RELEASE", *IMAGE_KEYS):
            require(key not in fields, "Duplicate release metadata key")
            fields[key] = value
    require(fields.get("LAGGENTE_RELEASE") == name, "Release id does not match metadata filename")
    for key in IMAGE_KEYS:
        value = fields.get(key, "")
        require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]*", value)), "Invalid application image reference")
    return fields


def pointer(root, name):
    directory = root / "releases"
    path = directory / (name + ".env")
    require(path.is_symlink(), "Missing release pointer: " + name)
    target = path.resolve(strict=True)
    require(target.parent == directory.resolve(), "Release pointer leaves release directory")
    release(root, target.stem)
    return target.stem


def repository(ref):
    name = ref.split("@", 1)[0]
    prefix, separator, last = name.rpartition("/")
    return prefix + separator + last.split(":", 1)[0]


def snapshot(containers):
    return sorted((c["Id"], c["Image"], c["State"]["StartedAt"]) for c in containers)


def current_is_healthy(containers, ids):
    for service, key in zip(("api", "gateway", "backup"), IMAGE_KEYS):
        matches = [c for c in containers if c.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") == "laggente" and c["Config"]["Labels"].get("com.docker.compose.service") == service]
        require(len(matches) == 1, "Expected one current LAGGENTE " + service + " container")
        container = matches[0]
        require(container["Image"] == ids[key], "Current pointer differs from running " + service)
        require(container["State"]["Status"] == "running" and container["State"].get("Health", {}).get("Status") == "healthy", "Current " + service + " is not healthy")


def write_state(path, releases):
    fd, temporary = tempfile.mkstemp(prefix=".image-retention-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"schema_version": 1, "releases": releases}, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def retain(root, docker, *, apply=False, initialize=False, rollbacks=(), activate=None, verify=None):
    """Called only with deploy.lock held; dry runs neither write nor delete."""
    root = Path(root)
    if verify:
        record = release(root, verify)
        return {"verified_release": verify, "images": {key: docker.image_id(record[key]) for key in IMAGE_KEYS}}
    current = pointer(root, "current")
    state_path = root / "releases" / "image-retention.json"
    require(not state_path.is_symlink(), "Retention state must not be symlinked")
    if initialize:
        require(not state_path.exists(), "Retention is already initialized")
        require(len(rollbacks) <= 2 and len(set(rollbacks)) == len(rollbacks) and current not in rollbacks, "Specify up to two distinct rollback releases")
        kept = [current, *rollbacks]
    else:
        require(not rollbacks, "--rollback requires --initialize")
        if state_path.exists():
            state = json.loads(state_path.read_text())
            kept = state.get("releases", [])
            require(state.get("schema_version") == 1 and 1 <= len(kept) <= 3 and len(set(kept)) == len(kept), "Invalid retention state")
        else:
            # First-ever deployment can initialize itself; an existing installation
            # requires an explicit operator choice of its two rollback releases.
            records = [p for p in (root / "releases").glob("*.env") if not p.is_symlink()]
            require(activate == current and len(records) == 1, "Initialize retention with the selected rollback releases first")
            kept = []
        if activate:
            require(activate == current, "Activated release must match current.env")
            kept = [current, *[name for name in kept if name != current]][:3]
        require(kept[0] == current, "Retention state does not match current.env")
    previous = root / "releases" / "previous.env"
    if previous.exists() or previous.is_symlink():
        require(pointer(root, "previous") in kept, "The immediate rollback release must be retained")

    protected = {}
    for name in kept:
        record = release(root, name)
        protected[name] = {key: docker.image_id(record[key]) for key in IMAGE_KEYS}
    protected_ids = {i for images in protected.values() for i in images.values()}
    containers = docker.containers()
    current_is_healthy(containers, protected[current])
    in_use = {c["Image"] for c in containers}
    known_repositories = set()
    for path in (root / "releases").glob("*.env"):
        if not path.is_symlink():
            known_repositories.update(repository(release(root, path.stem)[key]) for key in IMAGE_KEYS)
    candidate_ids = {}
    for image in docker.images():
        if image["Id"] in protected_ids or image["Id"] in in_use:
            continue
        for tag in image.get("RepoTags") or []:
            if repository(tag) in known_repositories:
                candidate_ids[tag] = image["Id"]
    candidates = sorted(candidate_ids)
    result = {"apply": apply, "retained_releases": kept, "retained_image_ids": protected, "remove_refs": candidates, "removed_refs": []}
    if apply:
        # Recheck every retained reference and the live pointers before the first deletion.
        require(pointer(root, "current") == current, "Current release changed during planning")
        require(snapshot(docker.containers()) == snapshot(containers), "Containers changed during planning")
        for name in kept:
            record = release(root, name)
            require({key: docker.image_id(record[key]) for key in IMAGE_KEYS} == protected[name], "Retained image reference changed during planning")
        write_state(state_path, kept)
        for ref in candidates:
            require(docker.image_id(ref) == candidate_ids[ref], "Candidate image reference changed during cleanup")
            docker.remove(ref)
            result["removed_refs"].append(ref)
        for name in kept:
            record = release(root, name)
            require({key: docker.image_id(record[key]) for key in IMAGE_KEYS} == protected[name], "Retained image changed after cleanup")
        require(snapshot(docker.containers()) == snapshot(containers), "Containers changed during cleanup")
        current_is_healthy(docker.containers(), protected[current])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("LAGGENTE_ROOT", "/opt/laggente")))
    parser.add_argument("--apply", action="store_true", help="write retention state and remove planned image references")
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--rollback", action="append", default=[])
    parser.add_argument("--activate")
    parser.add_argument("--verify-release")
    parser.add_argument("--lock-fd", type=int, help="inherit the deployer's already open lock descriptor")
    args = parser.parse_args()
    lock_path = args.root / "deploy.lock"
    if args.lock_fd is None:
        lock = lock_path.open("a")
        lock_fd = lock.fileno()
    else:
        lock_fd = args.lock_fd
        require(os.fstat(lock_fd).st_ino == lock_path.stat().st_ino and os.fstat(lock_fd).st_dev == lock_path.stat().st_dev, "Incorrect deployment lock descriptor")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise RetentionError("Another LAGGENTE deployment or cleanup is running") from error
    print(json.dumps(retain(args.root, Docker(), apply=args.apply, initialize=args.initialize, rollbacks=args.rollback, activate=args.activate, verify=args.verify_release), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RetentionError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise SystemExit("image retention: " + str(error))
