"""Run pinned upstream mouse scanner regression fixtures against Keke modules."""
from pathlib import Path
import sys,types,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
source=ROOT/'.planning/2026-09-28-cocoa-assistant-ui-overhaul/artifacts/nte-analysis-2026-10-07/public-source/tests/test_mouse_inventory_scanner.py'
module=types.ModuleType('keke_upstream_mouse_tests');module.__file__=str(source)
sys.modules[module.__name__]=module
exec(compile(source.read_text(encoding='utf-8').replace('src.','vision.upstream.'),str(source),'exec'),module.__dict__)
suite=unittest.defaultTestLoader.loadTestsFromModule(module)
result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
