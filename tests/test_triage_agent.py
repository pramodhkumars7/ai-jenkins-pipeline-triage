import json
import sys
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Stub agent_tools before importing triage_agent
_saved_agent_tools = sys.modules.get("agent_tools")
sys.modules["agent_tools"] = MagicMock()
import triage_agent
if _saved_agent_tools is not None:
    sys.modules["agent_tools"] = _saved_agent_tools
else:
    sys.modules.pop("agent_tools", None)


class TestDetectErrorClass(unittest.TestCase):
    def test_detects_oomkilled(self):
        self.assertEqual(triage_agent.detect_error_class("OOMKilled pod", ""), "OOMKilled")

    def test_detects_crashloop(self):
        self.assertEqual(triage_agent.detect_error_class("CrashLoopBackOff x7", ""), "CrashLoopBackOff")

    def test_detects_imagepull(self):
        self.assertEqual(triage_agent.detect_error_class("ImagePullBackOff", ""), "ImagePullBackOff")

    def test_detects_readiness(self):
        self.assertEqual(triage_agent.detect_error_class("ReadinessProbeFailed", ""), "ReadinessProbeFailed")

    def test_detects_from_rca_when_not_in_log(self):
        self.assertEqual(triage_agent.detect_error_class("some log", "root cause is OOMKilled"), "OOMKilled")

    def test_unknown_when_no_match(self):
        self.assertEqual(triage_agent.detect_error_class("generic error", "something broke"), "Unknown")


class TestApplyEksFix(unittest.TestCase):
    _MANIFEST = """\
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: myapp
        image: myapp:v2.3.1
        resources:
          limits:
            memory: "256Mi"
        env: []
        readinessProbe:
          initialDelaySeconds: 10
          failureThreshold: 3
"""

    def _write_manifest(self, tmp_dir: str) -> pathlib.Path:
        p = pathlib.Path(tmp_dir) / "k8s" / "deployment.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self._MANIFEST)
        return p

    def test_oomkilled_increases_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._write_manifest(tmp)
            orig_cwd = pathlib.Path.cwd()
            import os; os.chdir(tmp)
            try:
                branch, msg, files = triage_agent.apply_eks_fix("OOMKilled")
                self.assertEqual(branch, "fix/eks-oomkilled-increase-memory")
                self.assertIn("512Mi", manifest.read_text())
                self.assertEqual(files, ["k8s/deployment.yaml"])
            finally:
                os.chdir(orig_cwd)

    def test_imagepull_updates_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._write_manifest(tmp)
            import os; orig = pathlib.Path.cwd(); os.chdir(tmp)
            try:
                branch, msg, files = triage_agent.apply_eks_fix("ImagePullBackOff")
                self.assertIn("v2.3.2", manifest.read_text())
            finally:
                os.chdir(orig)

    def test_readiness_updates_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._write_manifest(tmp)
            import os; orig = pathlib.Path.cwd(); os.chdir(tmp)
            try:
                triage_agent.apply_eks_fix("ReadinessProbeFailed")
                content = manifest.read_text()
                self.assertIn("failureThreshold: 6", content)
                self.assertIn("initialDelaySeconds: 30", content)
            finally:
                os.chdir(orig)

    def test_crashloop_adds_db_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._write_manifest(tmp)
            import os; orig = pathlib.Path.cwd(); os.chdir(tmp)
            try:
                triage_agent.apply_eks_fix("CrashLoopBackOff")
                self.assertIn("DATABASE_URL", manifest.read_text())
            finally:
                os.chdir(orig)

    def test_unknown_returns_no_branch(self):
        branch, msg, files = triage_agent.apply_eks_fix("Unknown")
        self.assertIsNone(branch)
        self.assertEqual(files, [])


class TestApplyPlaywrightFix(unittest.TestCase):
    _CONFIG = "module.exports = { timeout: 30000, use: {} };"

    def test_increases_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "playwright.config.js"
            config.write_text(self._CONFIG)
            import os; orig = pathlib.Path.cwd(); os.chdir(tmp)
            try:
                branch, msg, files = triage_agent.apply_playwright_fix()
                self.assertEqual(branch, "fix/playwright-increase-timeout")
                self.assertIn("60000", config.read_text())
            finally:
                os.chdir(orig)

    def test_no_change_when_timeout_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "playwright.config.js"
            config.write_text("module.exports = {};")
            import os; orig = pathlib.Path.cwd(); os.chdir(tmp)
            try:
                branch, msg, files = triage_agent.apply_playwright_fix()
                self.assertIsNone(branch)
            finally:
                os.chdir(orig)


class TestGetRca(unittest.TestCase):
    def test_returns_stdout_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Root cause: OOMKilled due to low memory limit."
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            rca = triage_agent.get_rca("some log", "eks-deploy")
        self.assertEqual(rca, "Root cause: OOMKilled due to low memory limit.")
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "gh")
        self.assertEqual(call_args[1], "copilot")
        self.assertEqual(call_args[2], "explain")

    def test_raises_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "auth error"
        with patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(RuntimeError):
                triage_agent.get_rca("some log", "eks-deploy")


if __name__ == "__main__":
    unittest.main()
