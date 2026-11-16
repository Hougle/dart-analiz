import importlib
import os
import sys
import tempfile
import time
import unittest

import freshness

NAMES = ("fresh_a", "fresh_b")


class DropStaleModules(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name, body in zip(NAMES, ("def f(x):\n    return 1\n", "VALUE = 1\n")):
            with open(os.path.join(self.dir, name + ".py"), "w") as fh:
                fh.write(body)
        sys.path.insert(0, self.dir)
        self._import()

    def tearDown(self):
        sys.path.remove(self.dir)
        for n in NAMES:
            sys.modules.pop(n, None)

    def _import(self):
        importlib.invalidate_caches()
        for n in NAMES:
            importlib.import_module(n)

    def test_first_check_in_a_process_reloads_once(self):
        # Modules loaded before the first check may be older than the files on disk.
        self.assertEqual(freshness.drop_stale_modules(self.dir), list(NAMES))
        self._import()
        self.assertEqual(freshness.drop_stale_modules(self.dir), [])
        self.assertIn("fresh_a", sys.modules)

    def test_changed_file_drops_every_project_module(self):
        freshness.drop_stale_modules(self.dir)
        self._import()
        freshness.drop_stale_modules(self.dir)      # nothing changed: modules are now known
        path = os.path.join(self.dir, "fresh_a.py")
        with open(path, "w") as fh:
            fh.write("def f(x, matches=None):\n    return 2\n")
        later = time.time() + 5
        os.utime(path, (later, later))
        self.assertEqual(freshness.drop_stale_modules(self.dir), list(NAMES))
        self.assertNotIn("fresh_b", sys.modules)
        self._import()
        self.assertEqual(sys.modules["fresh_a"].f(0, matches=1), 2)   # the new version
        self.assertEqual(freshness.drop_stale_modules(self.dir), [])


if __name__ == "__main__":
    unittest.main()
