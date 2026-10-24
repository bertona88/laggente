import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "retain-production-images.py"
spec = importlib.util.spec_from_file_location("retention", SCRIPT)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class FakeDocker:
    def __init__(self):
        self.refs = {}
        self.removed = []
        self.live = []

    def image_id(self, ref):
        retention.require(ref in self.refs, "Missing local image")
        return self.refs[ref]

    def images(self):
        return [{"Id": image, "RepoTags": [ref for ref, value in self.refs.items() if value == image]}
                for image in set(self.refs.values())]

    def containers(self):
        return self.live

    def remove(self, ref):
        self.removed.append(ref)
        del self.refs[ref]


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "releases").mkdir()
        self.docker = FakeDocker()
        for name in ["old", "a", "b", "c"]:
            self.add_release(name)
        self.docker.refs["postgres:16-alpine"] = "postgres"
        self.docker.refs["unrelated-api:old"] = "unrelated"
        self.point("current", "c")
        self.point("previous", "b")
        self.activate_containers("c")

    def add_release(self, name):
        fields = {"LAGGENTE_RELEASE": name}
        for key, service in zip(retention.IMAGE_KEYS, ["api", "gateway", "backup"]):
            ref = "laggente-" + service + ":" + name
            fields[key] = ref
            self.docker.refs[ref] = service + "-" + name
        (self.root / "releases" / (name + ".env")).write_text("\n".join(k + "=" + v for k, v in fields.items()))

    def point(self, pointer, name):
        path = self.root / "releases" / (pointer + ".env")
        path.unlink(missing_ok=True)
        path.symlink_to(name + ".env")

    def activate_containers(self, name):
        self.docker.live = [{"Id": service, "Image": service + "-" + name,
                             "Config": {"Labels": {"com.docker.compose.project": "laggente", "com.docker.compose.service": service}},
                             "State": {"StartedAt": "unchanged", "Status": "running", "Health": {"Status": "healthy"}}}
                            for service in ["api", "gateway", "backup"]]

    def initialize(self, apply=True):
        return retention.retain(self.root, self.docker, initialize=True, rollbacks=["b", "a"], apply=apply)

    def test_dry_run_preserves_images_and_does_not_create_state(self):
        result = self.initialize(apply=False)
        self.assertEqual(result["retained_releases"], ["c", "b", "a"])
        self.assertEqual(set(result["remove_refs"]), {"laggente-" + service + ":old" for service in ["api", "gateway", "backup"]})
        self.assertFalse(self.docker.removed)
        self.assertFalse((self.root / "releases/image-retention.json").exists())

    def test_apply_preserves_three_complete_sets_foundation_and_other_apps(self):
        self.initialize()
        self.assertEqual(len(self.docker.removed), 3)
        self.assertIn("postgres:16-alpine", self.docker.refs)
        self.assertIn("unrelated-api:old", self.docker.refs)
        for name in ["c", "b", "a"]:
            retention.retain(self.root, self.docker, verify=name)
        self.assertTrue((self.root / "releases/old.env").exists())

    def test_successful_deployment_rotates_only_after_activation(self):
        self.initialize()
        self.add_release("d")
        self.point("current", "d")
        self.point("previous", "c")
        self.activate_containers("d")
        result = retention.retain(self.root, self.docker, activate="d", apply=True)
        self.assertEqual(result["retained_releases"], ["d", "c", "b"])
        self.assertNotIn("laggente-api:a", self.docker.refs)

    def test_successful_rollback_promotes_target_and_keeps_old_current(self):
        self.initialize()
        self.point("current", "a")
        self.point("previous", "c")
        self.activate_containers("a")
        result = retention.retain(self.root, self.docker, activate="a", apply=True)
        self.assertEqual(result["retained_releases"], ["a", "c", "b"])

    def test_missing_rollback_image_aborts_before_any_write_or_deletion(self):
        del self.docker.refs["laggente-backup:a"]
        with self.assertRaises(retention.RetentionError):
            self.initialize()
        self.assertFalse(self.docker.removed)
        self.assertFalse((self.root / "releases/image-retention.json").exists())

    def test_unhealthy_current_aborts_before_deletion(self):
        self.docker.live[0]["State"]["Health"]["Status"] = "unhealthy"
        with self.assertRaises(retention.RetentionError):
            self.initialize()
        self.assertFalse(self.docker.removed)

    def test_any_container_protects_its_image_even_when_stopped(self):
        self.docker.live.append({"Id": "stopped", "Image": "api-old", "Config": {"Labels": {}},
                                 "State": {"StartedAt": "old", "Status": "exited"}})
        self.initialize()
        self.assertIn("laggente-api:old", self.docker.refs)

    def test_foreign_alias_is_not_deleted(self):
        self.docker.refs["another-project:shared"] = "api-old"
        self.initialize()
        self.assertIn("another-project:shared", self.docker.refs)
        self.assertNotIn("laggente-api:old", self.docker.refs)

    def test_alias_of_protected_image_cannot_delete_retained_digest(self):
        self.docker.refs["laggente-api:local"] = "api-a"
        self.initialize()
        self.assertIn("laggente-api:local", self.docker.refs)

    def test_pruned_release_is_refused_before_rollback(self):
        self.initialize()
        with self.assertRaises(retention.RetentionError):
            retention.retain(self.root, self.docker, verify="old")

    def test_existing_installation_requires_explicit_history(self):
        with self.assertRaises(retention.RetentionError):
            retention.retain(self.root, self.docker, activate="c", apply=True)
        self.assertFalse(self.docker.removed)

    def test_malformed_metadata_is_not_executed_or_used_for_deletion(self):
        path = self.root / "releases/old.env"
        path.write_text(path.read_text().replace("laggente-api:old", "$(touch /should-not-exist)"))
        with self.assertRaises(retention.RetentionError):
            self.initialize()
        self.assertFalse(self.docker.removed)

    def test_previous_pointer_must_be_retained(self):
        with self.assertRaises(retention.RetentionError):
            retention.retain(self.root, self.docker, initialize=True, rollbacks=["a", "old"], apply=True)
        self.assertFalse(self.docker.removed)

    def test_concurrent_deployment_lock_blocks_cli_before_docker(self):
        with (self.root / "deploy.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another LAGGENTE deployment", result.stderr)

    def test_registry_port_and_digest_repository_matching(self):
        self.assertEqual(retention.repository("localhost:5000/org/laggente-api@sha256:abc"), "localhost:5000/org/laggente-api")

    def test_retagged_candidate_aborts_instead_of_deleting_protected_image(self):
        images = self.docker.images
        def changed_images():
            result = images()
            self.docker.refs["laggente-api:old"] = "api-a"
            return result
        self.docker.images = changed_images
        with self.assertRaises(retention.RetentionError):
            self.initialize()
        self.assertFalse(self.docker.removed)


if __name__ == "__main__":
    unittest.main()
