import unittest
from pathlib import Path


class RunScriptCompatibilityTests(unittest.TestCase):
    def test_run_script_is_ascii_for_windows_powershell_compatibility(self):
        script_path = Path(__file__).resolve().parents[1] / "run.ps1"

        script = script_path.read_bytes().decode("ascii")

        self.assertIn("uvicorn classroom_simulator.main:app", script)
        self.assertIn(".venv\\Scripts\\python.exe", script)


if __name__ == "__main__":
    unittest.main()
