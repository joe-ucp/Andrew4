"""Verify the distributed local package bytes; this is not scientific certification."""
from pathlib import Path
import json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
def require(condition,message):
    if not condition:raise ValueError(message)
def unique_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate manifest JSON key: '+key)
        result[key]=value
    return result
def verify(root=ROOT):
    root=Path(root).resolve()
    manifest=json.loads((root/'artifact_manifest.json').read_text(encoding='utf8'),object_pairs_hook=unique_object)
    require(manifest.get('schema_version')=='1.0','Unsupported manifest schema')
    require(type(manifest.get('artifacts')) is list and bool(manifest['artifacts']),'Invalid artifact list')
    seen=set()
    for row in manifest['artifacts']:
        require(type(row) is dict,'Invalid artifact record')
        name=row.get('path')
        require(type(name) is str and bool(name),'Invalid manifest path')
        require('\\' not in name and ':' not in name and not name.startswith('/') and all(s not in ('','.', '..') for s in name.split('/')),'Unsafe manifest path: '+name)
        normalized=name.casefold()
        require(normalized not in seen,'Duplicate manifest path: '+name)
        seen.add(normalized)
        p=(root/row['path']).resolve()
        require(p.is_relative_to(root),'Unsafe manifest path: '+name)
        require(p.is_file(),'Missing artifact: '+name)
        require(type(row.get('size_bytes')) is int and row['size_bytes']>=0,'Invalid artifact size: '+name)
        require(p.stat().st_size==row['size_bytes'],'Size mismatch: '+name)
        require(type(row.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'Invalid SHA256: '+name)
        require(hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'Hash mismatch: '+name)
    required={'manuscript/paper.pdf','manuscript/paper.docx','manuscript/paper.tex','sources.tsv','geometry_ledger.csv','model_specification.json','data/delivery_response.csv','data/dose_area_frontier.csv','REPORT.md','README.md','reproduce.py'}
    require(required <= {r['path'] for r in manifest['artifacts']},'Required artifact relationship missing')
    revised={'robustness_specification.json','code/robustness.py','data/robustness_map.csv','data/robustness_targets.csv','evidence/robustness_verification.json','RESPONSE_TO_REVIEW.md'}
    require(revised <= {r['path'] for r in manifest['artifacts']},'Required revision2 relationship missing')
    focused={'design_constraints_specification.json','code/design_constraints.py','data/design_constraints_maxima.csv','data/design_constraints_targets.csv','data/mechanism_comparison.csv','evidence/design_constraints_verification.json'}
    require(focused <= {r['path'] for r in manifest['artifacts']},'Required revision3 relationship missing')
    repair={'reproduction_comparison_specification.json','code/reproduction_contract.py'}
    require(repair <= {r['path'] for r in manifest['artifacts']},'Required regeneration comparison contract missing')
    print(f'PASS: {len(manifest["artifacts"])} artifact hashes and required relationships verified; no certificate or scientific validity implied')
if __name__=='__main__':verify()
