#!/usr/bin/env python3
"""Rehearse a synthetic DRM-to-PEG handoff with explicit stop conditions."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Rehearsal:
    def __init__(self, drm: Path, peg: Path, output: Path):
        self.drm=drm.resolve(strict=True);self.peg=peg.resolve(strict=True)
        self.output=output.resolve();self.output.mkdir(parents=True,exist_ok=False)
        self.commands=[]

    def call(self, tool: str, args: list, expected: int | None = 0):
        executable={'drm':self.drm,'peg':self.peg,'python':Path(sys.executable)}[tool]
        env=dict(os.environ)
        for name in ('PYTHONPATH','PYTHONHOME'):
            env.pop(name,None)
        env['PYTHONSAFEPATH']='1'
        result=subprocess.run([str(executable),*map(str,args)],capture_output=True,text=True,
                              cwd=self.output,timeout=60,check=False,env=env)
        self.commands.append({'tool':tool,'argv':[str(executable),*map(str,args)],
                              'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        (self.output/'commands.json').write_text(json.dumps(self.commands,indent=2)+'\n')
        if expected is not None:require(result.returncode==expected,'Unexpected exit; inspect commands.json.')
        return result

    def consume_verified(self, pack: Path, output: Path):
        # Do not infer a successful import from an existing graph file. This
        # helper is reached only after a successful producer call in run().
        verified=self.call('drm',['handoff','verify',pack],expected=None)
        if verified.returncode!=0:
            return {'state':'stopped_before_consumer','reason':'handoff_verification_failed'}
        require(json.loads(verified.stdout).get('valid') is True,'Verifier did not establish byte integrity.')
        self.call('peg',['import-relationship',pack/'artifact-index.json','--output',output])
        graph=json.loads(output.read_text());diagnostics=graph['relationship_import_diagnostics']
        index=json.loads((pack/'artifact-index.json').read_text());nodes={n['id']:n for n in graph['nodes']}
        for item in index['objects']+index['relationships']:
            received=nodes[item['artifact_ref']]
            require(received.get('observed_at')==index['observed_at'],'Observation time changed across the handoff.')
            if 'provenance' in item:
                require(received['metadata'].get('provenance')==item['provenance'],'Source-row provenance changed.')
        require(diagnostics['valid'] is True,'Consumer reported invalid relationship index.')
        self.call('peg',['analyze',output])
        review=json.loads(self.call('peg',['review',output]).stdout)
        self.call('peg',['review',output,'--markdown',output.with_suffix('.md')])
        require(review['raw_coverage']['requirements']==0,'Unexpected authored requirements.')
        markdown=output.with_suffix('.md').read_text()
        require('No requirements were supplied.' in markdown and 'n/a' in markdown,
                'Empty scope is not displayed explicitly.')
        return {'state':'consumed','native_policy_passed':diagnostics['source_policy_passed'],
                'observation_time_status':diagnostics['observation_time_status'],
                'evidence_nodes':sum(n['type']=='evidence' for n in graph['nodes']),
                'defect_nodes':sum(n['type']=='defect' for n in graph['nodes']),
                'peg_policy_decision':review['decision'],'requirements':0,
                'authority':'No business acceptance, migration or replay permission.'}

    def handoff_after_import(self, imported, accounting: dict, graph: Path,
                             pack: Path, *, focus: str, policy: Path, observed: str):
        if imported.returncode != 0 or accounting.get('complete') is not True or accounting.get('model_returned') is not True:
            return {'state':'stopped_before_handoff_and_consumer', 'reason':'producer_not_complete'}
        self.call('drm',['validate',graph])
        self.call('drm',['handoff','build',graph,pack,'--focus',focus,
                         '--policy',policy,'--max-depth','2','--observed-at',observed])
        return self.consume_verified(pack,pack.parent/'project.json')

    def run(self):
        source=Path(__file__).resolve().parents[1]; rows=[]; packs=[]
        observed='2026-08-25T10:00:00Z'  # Authored fixture time, not today's measurement.
        for case,contents in [('clear','4711,7200311,10000345\n4712,7200312,10000346\n'),
                              ('cardinality_findings','4711,7200311,10000345\n4711,7200312,10000346\n')]:
            d=self.output/case;d.mkdir();manifest=json.loads((source/'examples/csv/manifest.json').read_text())
            # Strengthen only the authored fixture component requirements.
            for spec in manifest['node_sources']+manifest['relationship_sources']:
                spec['required_identity_columns']=['AFS_KUNNR','MDG_BP','S4_BP']
            (d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            (d/'customer_crosswalk.csv').write_text('AFS_KUNNR,MDG_BP,S4_BP\n'+contents)
            graph=d/'graph.json'; report=d/'import-report.json'
            imported=self.call('drm',['import-csv',d/'manifest.json','--output',graph,'--import-report',report])
            accounting=json.loads(report.read_text())
            require(accounting['complete'] is True and accounting['model_returned'] is True,
                    'Import accounting did not establish a complete producer run.')
            require(accounting['counts']=={'encountered':10,'accepted':10,'skipped':0,'rejected':0},'Unexpected source-declaration accounting.')
            pack=d/'handoff';packs.append(pack)
            consumed=self.handoff_after_import(imported,accounting,graph,pack,focus='AFS:4711',
                                               policy=source/'examples/identity-policy.json',observed=observed)
            manifest_out=json.loads((pack/'manifest.json').read_text())
            require('import-report.json' not in manifest_out['files'],'Unexpected sidecar binding contract.')
            require(consumed['state']=='consumed','Valid synthetic handoff was not consumed.')
            require(consumed['defect_nodes']==0 if case=='clear' else consumed['defect_nodes']>0,
                    'Expected relationship policy distinction disappeared.')
            native=json.loads((pack/'investigation.json').read_text())
            rows.append({'case':case,'state':consumed['state'],'import_complete':True,
                         'accounting_counts':accounting['counts'],'counting_unit':accounting['counting_unit'],
                         'native_status':native['status'],'pack_id':manifest_out['pack_id'],
                         'pack_sha256':sha(pack/'manifest.json'),'consumer':consumed,
                         'sidecar_in_handoff':False})
        # An intentionally changed *copy* cannot be passed to PEG as verified.
        damaged=self.output/'changed-pack';shutil.copytree(packs[0],damaged)
        with (damaged/'artifact-index.json').open('ab') as handle:handle.write(b' ')
        before=len(self.commands);result=self.consume_verified(damaged,self.output/'changed-project.json')
        require(result['state']=='stopped_before_consumer','Changed bytes did not stop the consumer.')
        require(all(c['tool']!='peg' for c in self.commands[before:]),'Consumer ran after verification failure.')
        require(not (self.output/'changed-project.json').exists(),'Unexpected consumer output on failed verification.')
        rows.append({'case':'changed_handoff_bytes',**result,'peg_calls':0})
        # Preserve the old graph after a failed refresh, but stop before exporting
        # it as if the new source had been imported successfully.
        inputs=self.output/'xlsx-inputs'
        self.call('python',[source/'examples/xlsx-layout/generate.py',inputs])
        d=self.output/'failed_refresh';d.mkdir();graph=d/'graph.json'
        self.call('drm',['import-xlsx',inputs/'valid.json','--output',graph,'--import-report',d/'initial-report.json'])
        before_hash=sha(graph);before=len(self.commands)
        failed=self.call('drm',['import-xlsx',inputs/'duplicate-cell.json','--output',graph,
                               '--import-report',d/'failed-report.json'],expected=None)
        require(failed.returncode==2,'Expected rejected refresh with exit 2.')
        accounting=json.loads((d/'failed-report.json').read_text())
        require(accounting['complete'] is False and accounting['status']=='aborted','Expected an aborted report.')
        stopped=self.handoff_after_import(failed,accounting,graph,d/'handoff',focus='SYNTHETIC:00120',
                                          policy=source/'examples/identity-policy.json',observed=observed)
        require(stopped['state']=='stopped_before_handoff_and_consumer','Aborted producer reached downstream work.')
        require(sha(graph)==before_hash,'Failed refresh changed the previously saved graph.')
        require(not (d/'handoff').exists() and not (d/'project.json').exists(),'Unexpected downstream output after abort.')
        require(all(c['tool']!='peg' for c in self.commands[before:]),'Consumer ran after producer failure.')
        rows.append({'case':'failed_xlsx_refresh','state':'stopped_before_handoff_and_consumer',
                     'producer_exit':2,'import_status':accounting['status'],'old_graph_sha256':before_hash,
                     'old_graph_unchanged':True,'old_graph_revalidated':False,'peg_calls':0})
        result={'status':'passed','cases':rows,'cli_invocations':sum(c['tool']!='python' for c in self.commands),
                'fixture_generator_calls':sum(c['tool']=='python' for c in self.commands),
                'fixture_observed_at':observed,'limits':['Synthetic fixture observation time, not live source freshness.',
                'Import sidecar is separate from the verified handoff, not a transaction or attestation.',
                'Verify checks retained bytes, not authenticity or source completeness.',
                'PEG PASS with zero requirements does not clear producer findings or grant acceptance.',
                'Serial local rehearsal; no concurrent mutation protection or production orchestration.']}
        (self.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drm-cli',type=Path,required=True)
    parser.add_argument('--peg-cli',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(Rehearsal(args.drm_cli,args.peg_cli,args.output).run(),indent=2))
