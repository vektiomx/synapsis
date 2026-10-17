"""Benchmark isolation: generated code cannot read or replace the hidden oracle."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('coding_evaluation',Path(__file__).resolve().parents[1]/'tools/evaluate_coding_memory.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CodingEvaluationIntegrity(unittest.TestCase):
    def test_pure_branching_policy_is_admitted(self):
        module.validate_source("def policy(context):\n    return 47 if context.get('fast_lane') else 83\n")

    def test_oracle_access_import_decorator_or_indirect_call_is_rejected(self):
        for source in ("import pathlib\ndef policy(context): return 47", "@context.get('decorate')\ndef policy(context): return 47", "def policy(context): return open('tests/test_hidden.py').read()", "def policy(context): return context.__class__", "def policy(context):\n f=context.get\n return f('a')", "def policy(context): return __import__('os').getcwd()"):
            with self.subTest(source=source),self.assertRaises(ValueError):module.validate_source(source)

if __name__=='__main__':unittest.main()
