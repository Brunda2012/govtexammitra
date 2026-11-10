import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

def run(module_name, out_path):
    import importlib
    m = importlib.import_module(module_name)
    stream = io.StringIO()
    r = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(m))
    with open(out_path, "w") as f:
        f.write(stream.getvalue() + f"\nRESULT: {r.testsRun} tests, {len(r.failures)} failures, {len(r.errors)} errors\n")
    return len(r.failures) + len(r.errors)

bad = 0
for name, out in (("test_engine", "test_results.txt"), ("test_api", "test_api_results.txt"),
                  ("test_govsource", "test_govsource_results.txt"),
                  ("test_features", "test_features_results.txt")):
    try:
        bad += run(name, os.path.join(HERE, out))
    except Exception:
        import traceback
        with open(os.path.join(HERE, out), "w") as f:
            f.write("CRASH\n" + traceback.format_exc())
        bad += 1
sys.exit(0)
