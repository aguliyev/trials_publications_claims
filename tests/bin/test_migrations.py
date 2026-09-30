import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


class MigrationScriptsTestCase(TestCase):
    def setUp(self):
        self.project = Path(__file__).resolve().parents[2]

    def test_makemigrations_runs_docker_compose_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            log = Path(tmp) / "docker.log"
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "DOCKER_LOG": str(log)}

            subprocess.run(["bash", str(self.project / "bin/makemigrations"), "core", "--empty"], env=env, check=True, capture_output=True)

            calls = log.read_text()
            self.assertIn("compose --env-file etc/.env exec django-app python django_app/manage.py makemigrations core --empty", calls)

    def test_migrate_runs_docker_compose_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            log = Path(tmp) / "docker.log"
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "DOCKER_LOG": str(log)}

            subprocess.run(["bash", str(self.project / "bin/migrate"), "core", "zero"], env=env, check=True, capture_output=True)

            calls = log.read_text()
            self.assertIn("compose --env-file etc/.env exec django-app python django_app/manage.py migrate core zero", calls)
