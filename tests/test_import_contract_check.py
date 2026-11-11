"""The CI checker must reject self-inconsistent reports, not just count summaries."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_import_report_contract.py'
spec = importlib.util.spec_from_file_location('import_contract_check', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ImportContractCheckTests(unittest.TestCase):
    def report(self):
        counts = dict(encountered=1, accepted=1, skipped=0, rejected=0)
        return dict(format='data-relationship-map-import-report/1.0', status='complete', complete=True,
                    model_returned=True, counts=counts, sources=[dict(counts=dict(counts), records=[dict(disposition='accepted')])])

    def test_valid_report_passes(self):
        report = self.report()
        self.assertIs(checker.validate_report(report, dict(report['counts']), 'complete'), report)

    def test_source_summary_cannot_hide_records(self):
        report = self.report();expected=dict(report['counts'])
        report['sources'][0]['counts'] = dict(encountered=0,accepted=0,skipped=0,rejected=0)
        with self.assertRaisesRegex(checker.ContractError,'source counts'): checker.validate_report(report,expected,'complete')

    def test_global_totals_must_reconcile_with_all_sources(self):
        report=self.report();expected=dict(report['counts'])
        report['sources'].append(deepcopy(report['sources'][0]))
        with self.assertRaisesRegex(checker.ContractError,'global totals'): checker.validate_report(report,expected,'complete')

    def test_invalid_count_types_and_dispositions_fail_closed(self):
        for bad in (-1, True, 1.0, '1'):
            for scope in ('global','source'):
                with self.subTest(bad=bad,scope=scope):
                    report=self.report();expected=dict(report['counts'])
                    target=report['counts'] if scope=='global' else report['sources'][0]['counts']
                    target['accepted']=bad
                    with self.assertRaises(checker.ContractError):checker.validate_report(report,expected,'complete')
        report=self.report();report['sources'][0]['records'][0]['disposition']='ignored'
        with self.assertRaises(checker.ContractError):checker.validate_report(report,dict(report['counts']),'complete')

    def test_status_and_missing_records_do_not_pass(self):
        for field,value in [('complete',False),('model_returned',False),('format','wrong'),('status','aborted')]:
            with self.subTest(field=field):
                report=self.report();expected=dict(report['counts']);report[field]=value
                with self.assertRaises(checker.ContractError):checker.validate_report(report,expected,'complete')
        report=self.report();report['sources'][0]['records']=[]
        with self.assertRaises(checker.ContractError):checker.validate_report(report,dict(report['counts']),'complete')


if __name__=='__main__':unittest.main()
