"""The optional synthetic rehearsal must stop before passing failed evidence on."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('rehearse_peg_handoff',ROOT/'scripts/rehearse_peg_handoff.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class HandoffRehearsalTests(unittest.TestCase):
    def stopped(self, code, report):
        runner=MODULE.Rehearsal.__new__(MODULE.Rehearsal)
        calls=[]
        runner.call=lambda *a,**k:calls.append((a,k))
        runner.consume_verified=lambda *a,**k:calls.append((a,k))
        result=runner.handoff_after_import(SimpleNamespace(returncode=code),report,
            Path('already-existing-graph'),Path('no-pack'),focus='SYNTHETIC',
            policy=Path('policy'),observed='2026-08-25T10:00:00Z')
        self.assertEqual(result['state'],'stopped_before_handoff_and_consumer')
        self.assertEqual(calls,[])

    def test_exit_two_stops_even_when_stale_sidecar_says_complete(self):
        self.stopped(2,{'complete':True,'model_returned':True})

    def test_other_nonzero_exit_stops(self):
        self.stopped(1,{'complete':True,'model_returned':True})

    def test_incomplete_zero_exit_stops(self):
        self.stopped(0,{'complete':False,'model_returned':True})

    def test_no_model_stops(self):
        self.stopped(0,{'complete':True,'model_returned':False})

    def test_missing_state_stops(self):
        self.stopped(0,{})

    def test_truthy_strings_are_not_complete(self):
        self.stopped(0,{'complete':'true','model_returned':'true'})

    def test_failed_verification_never_calls_consumer(self):
        runner=MODULE.Rehearsal.__new__(MODULE.Rehearsal);calls=[]
        def call(tool,args,expected=None):
            calls.append((tool,args));return SimpleNamespace(returncode=1,stdout='{}')
        runner.call=call
        result=runner.consume_verified(Path('pack'),Path('out'))
        self.assertEqual(result['state'],'stopped_before_consumer')
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'drm')

    def test_zero_exit_without_valid_true_is_not_verification(self):
        runner=MODULE.Rehearsal.__new__(MODULE.Rehearsal);calls=[]
        def call(tool,args,expected=None):
            calls.append((tool,args));return SimpleNamespace(returncode=0,stdout=json.dumps({'valid':'true'}))
        runner.call=call
        with self.assertRaises(RuntimeError):runner.consume_verified(Path('pack'),Path('out'))
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'drm')

    def test_subprocess_environment_does_not_override_installed_modules(self):
        runner=MODULE.Rehearsal.__new__(MODULE.Rehearsal)
        with tempfile.TemporaryDirectory() as d:
            runner.output=Path(d);runner.drm=Path('/trusted/drm');runner.peg=Path('/trusted/peg');runner.commands=[]
            with patch.dict(MODULE.os.environ,{'PYTHONPATH':'/untrusted','PYTHONHOME':'/other','PYTHONSAFEPATH':'0'}):
                with patch.object(MODULE.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{}',stderr='')) as call:
                    runner.call('drm',['help'])
            env=call.call_args.kwargs['env']
            self.assertNotIn('PYTHONPATH',env);self.assertNotIn('PYTHONHOME',env)
            self.assertEqual(env['PYTHONSAFEPATH'],'1')
