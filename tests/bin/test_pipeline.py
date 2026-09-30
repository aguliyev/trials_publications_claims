import logging
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch


STAGES = (
    ("ner", "save_ner_trials"),
    ("ner", "save_ner_publications"),
    ("interventions", "save_ner_interventions"),
    ("diseases", "save_ner_diseases"),
    ("claims", "save_claims"),
    ("judgement", "save_judgements"),
)


class PipelineScriptsTestCase(TestCase):
    def setUp(self):
        self.project = Path(__file__).resolve().parents[2]
        self.calls = []
        django = ModuleType("django")
        django.setup = lambda: self.calls.append("setup")
        lib = ModuleType("lib")
        lib.__path__ = []
        logs = ModuleType("lib.logs")
        logs.get_logger = lambda name: logging.getLogger(name)
        self.modules = {"django": django, "lib": lib, "lib.logs": logs}
        for module_name, function_name in STAGES:
            qualified_name = f"lib.{module_name}"
            module = self.modules.setdefault(qualified_name, ModuleType(qualified_name))
            def run(name=function_name):
                self.calls.append(name)

            run.__name__ = function_name
            setattr(module, function_name, run)

    def test_pipeline_sets_up_django_and_runs_stages_in_order(self):
        with patch.dict(sys.modules, self.modules), self.assertLogs("lib.jobs.pipeline", level="INFO") as log:
            runpy.run_path(str(self.project / "jobs/pipeline.py"), run_name="__main__")

        self.assertEqual(self.calls, ["setup", *(name for _, name in STAGES)])
        for _, name in STAGES:
            self.assertTrue(any(name in message for message in log.output))

    def test_pipeline_logs_failure_and_stops(self):
        def fail():
            self.calls.append("save_ner_diseases")
            raise ValueError("test failure")

        fail.__name__ = "save_ner_diseases"
        self.modules["lib.diseases"].save_ner_diseases = fail
        with patch.dict(sys.modules, self.modules), self.assertLogs("lib.jobs.pipeline", level="INFO") as log:
            with self.assertRaises(ValueError):
                runpy.run_path(str(self.project / "jobs/pipeline.py"), run_name="__main__")

        self.assertEqual(self.calls, ["setup", "save_ner_trials", "save_ner_publications",
                                      "save_ner_interventions", "save_ner_diseases"])
        self.assertTrue(any("save_ner_diseases" in message and "ERROR" in message for message in log.output))

    def test_launcher_executes_pipeline_in_running_django_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            log = Path(tmp) / "docker.log"
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "DOCKER_LOG": str(log)}

            subprocess.run(["bash", str(self.project / "bin/pipeline")], env=env, check=True, capture_output=True)

            self.assertEqual(log.read_text().splitlines(), [
                "compose", "--env-file", "etc/.env", "exec", "-T", "django-app", "python", "jobs/pipeline.py",
            ])
