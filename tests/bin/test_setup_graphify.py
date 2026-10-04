import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


class SetupGraphifyTestCase(TestCase):
    def setUp(self):
        self.project = Path(__file__).resolve().parents[2]

    def test_installs_graphify_hooks_from_the_active_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            executable_dir = Path(tmp) / "bin"
            executable_dir.mkdir()
            git_args = Path(tmp) / "git-args"
            git = executable_dir / "git"
            git.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GIT_ARGS"\nexit 0\n')
            git.chmod(0o755)
            invocation = Path(tmp) / "graphify-args"
            graphify = executable_dir / "graphify"
            graphify.write_text(
                '#!/bin/sh\n'
                'printf "%s\\n" "$*" >> "$GRAPHIFY_ARGS"\n'
                'if [ "$*" = "hook status" ]; then\n'
                '  printf "%s\\n" "post-commit: installed" "post-checkout: installed"\n'
                'fi\n'
            )
            graphify.chmod(0o755)
            environment = {
                **os.environ,
                "PATH": f"{executable_dir}:{os.environ['PATH']}",
                "GRAPHIFY_ARGS": str(invocation),
                "GIT_ARGS": str(git_args),
            }

            result = subprocess.run(
                ["bash", str(self.project / "bin/setup_graphify")],
                cwd=workspace,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(invocation.read_text(), "hook install\nhook status\n")
            self.assertEqual(
                git_args.read_text(),
                "rev-parse --is-inside-work-tree\n"
                "config --local --unset-all merge.graphify.name\n"
                "config --local --unset-all merge.graphify.driver\n",
            )
            self.assertIn("Graphify Git setup complete", result.stdout)

    def test_exits_with_installation_guidance_when_graphify_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            environment = {**os.environ, "PATH": "/usr/bin:/bin"}

            result = subprocess.run(
                ["bash", str(self.project / "bin/setup_graphify")],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Install the pinned development dependencies first", result.stderr)
