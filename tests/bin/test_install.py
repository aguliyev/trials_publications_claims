import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


class InstallTestCase(TestCase):
    def test_preloads_models_as_cache_owner_without_chown(self):
        project = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            log = Path(tmp) / "docker.log"
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "DOCKER_LOG": str(log)}

            subprocess.run(["bash", str(project / "bin/install")], env=env, check=True, capture_output=True)

            calls = log.read_text()
            self.assertIn("--user 1000:100 django-app sh -c", calls)
            self.assertIn("python bin/preload_models.py", calls)
            self.assertNotIn("chown", calls)
