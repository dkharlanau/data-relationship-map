import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

import drm_cli


class UnifiedCliTests(unittest.TestCase):
    def test_help_lists_investigation_commands(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = drm_cli.main(["--help"])
        self.assertEqual(result, 0)
        self.assertIn("lineage", output.getvalue())
        self.assertIn("artifacts", output.getvalue())

    def test_validate_dispatches_to_core(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = drm_cli.main(["validate", "examples/customer-chain.json"])
        self.assertEqual(result, 0)
        self.assertIn('"valid": true', output.getvalue())

    def test_path_dispatches_to_core(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = drm_cli.main(["path", "examples/customer-chain.json", "AFS:4711", "S4:10000891"])
        self.assertEqual(result, 0)
        self.assertIn("AFS:4711", output.getvalue())
        self.assertIn("S4:10000891", output.getvalue())

    def test_unknown_command_fails_loudly(self):
        error = io.StringIO()
        with redirect_stderr(error):
            result = drm_cli.main(["unknown"])
        self.assertEqual(result, 2)
        self.assertIn("Unknown command", error.getvalue())


if __name__ == "__main__":
    unittest.main()
