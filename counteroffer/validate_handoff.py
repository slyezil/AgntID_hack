#!/usr/bin/env python3
"""Offline integrity checks for the CounterOffer documentation pack.

This checks specification assets, NOT the future application or a live provider.
Run: python validate_handoff.py --report VALIDATION_REPORT.json
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    raise SystemExit('Install documentation-only dependencies: python -m pip install -r validation-requirements.txt')

ROOT = Path(__file__).resolve().parent
RESULTS: list[dict[str, Any]] = []

def check(name: str, condition: bool, detail: str = '') -> None:
    RESULTS.append({'check': name, 'passed': bool(condition), 'detail': detail})

def load(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def valid(schema: dict[str, Any], data: Any) -> bool:
    return not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data))

def walk_refs(node: Any):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == '$ref' and isinstance(v, str):
                yield v
            else:
                yield from walk_refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_refs(v)

def pointer(document: Any, ref: str) -> bool:
    if not ref.startswith('#/'):
        return False
    cur = document
    try:
        for key in ref[2:].split('/'):
            key = key.replace('~1', '/').replace('~0', '~')
            cur = cur[int(key)] if isinstance(cur, list) else cur[key]
        return True
    except (KeyError, IndexError, ValueError, TypeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    excluded = {'VALIDATION_REPORT.json', 'MANIFEST.json'}
    files = [p for p in ROOT.rglob('*') if p.is_file() and p.name not in excluded]
    json_files = [p for p in files if p.suffix == '.json']
    for p in json_files:
        try:
            json.loads(p.read_text())
            check(f'JSON parses: {p.relative_to(ROOT)}', True)
        except Exception as exc:
            check(f'JSON parses: {p.relative_to(ROOT)}', False, str(exc))
    for p in [p for p in files if p.suffix in ('.yaml', '.yml')]:
        try:
            yaml.safe_load(p.read_text())
            check(f'YAML parses: {p.relative_to(ROOT)}', True)
        except Exception as exc:
            check(f'YAML parses: {p.relative_to(ROOT)}', False, str(exc))
    for p in (ROOT / 'contracts').glob('*.schema.json'):
        try:
            Draft202012Validator.check_schema(json.loads(p.read_text()))
            check(f'JSON Schema valid: {p.name}', True)
        except Exception as exc:
            check(f'JSON Schema valid: {p.name}', False, str(exc))

    model = {t['name']: t for t in load('contracts/model-tools.json')['tools']}
    mcp = {t['name']: t for t in load('contracts/mcp-tools.json')['tools']}
    defs = load('contracts/tool-inputs.schema.json')['$defs']
    check('Exactly four intended tools', set(model) == {'search_products','get_availability','create_quote','get_quote'} == set(mcp))
    for name, tool in model.items():
        check(f'Model schema matches canonical definition: {name}', tool['inputSchema'] == defs[name])
        projected = copy.deepcopy(mcp[name]['inputSchema'])
        injected = projected['properties'].pop('_counteroffer_context', None)
        had_required = '_counteroffer_context' in projected.get('required', [])
        projected['required'] = [s for s in projected.get('required', []) if s != '_counteroffer_context']
        check(f'MCP context injection isolated: {name}', injected is not None and had_required and projected == tool['inputSchema'])

    create = model['create_quote']['inputSchema']
    for filename in ['allowed-quote-arguments.json','denied-quote-arguments.json','other-buyer-arguments.json']:
        check(f'Business schema accepts intended probe: {filename}', valid(create, load('fixtures/' + filename)))
    base = load('fixtures/allowed-quote-arguments.json')
    for bps, expected in [(0,True),(200,True),(300,True),(301,True),(1200,True),(10000,True),(-1,False),(10001,False),(True,False),('200',False),(200.5,False)]:
        data = dict(base, discount_bps=bps)
        check(f'Discount schema case {bps!r}', valid(create,data) == expected)
    data = dict(base, _counteroffer_context='not-model-controlled')
    check('Model cannot inject execution context', not valid(create,data))
    check('MCP requires execution context', not valid(mcp['create_quote']['inputSchema'],base))
    # Deliberately not a signed token: schema validation must not be confused with auth.
    data['_counteroffer_context'] = 'x' * 256
    check('MCP context-shaped example accepted structurally', valid(mcp['create_quote']['inputSchema'],data), 'Signature verification is a future application test, not done here.')
    for key, value in [('approved',True),('graphql','mutation X {}'),('unit_price',0),('rebate',100),('url','https://invalid.example')]:
        check(f'Unknown model argument rejected: {key}', not valid(create,dict(base,**{key:value})))
    for q, expected in [(0,False),(1,True),(10000,True),(10001,False),(True,False),('2',False),(1.5,False)]:
        data=copy.deepcopy(base); data['items'][0]['quantity']=q
        check(f'Quantity schema case {q!r}', valid(create,data)==expected)

    for fixture, schema in [('quote-example.json','quote.schema.json'),('event-example.json','event.schema.json'),('evidence-example.json','evidence.schema.json')]:
        check(f'Fixture validates: {fixture}',valid(load('contracts/'+schema),load('fixtures/'+fixture)))
    result_defs=load('contracts/tool-results.schema.json')['$defs']
    check('Quote result schema consistent', result_defs['QuoteResult']=={k:v for k,v in load('contracts/quote.schema.json').items() if k not in ['$schema','$id','title','description']})
    pending={'status':'PENDING','code':'PROVIDER_PENDING','operation_id':base.get('operation_id','5a51449b-1c4a-4bf4-b0d2-6dd7223bb48b'),'message':'Provider details still processing.','may_retry_write':False}
    check('Pending-result contract validates',valid(result_defs['PendingResult'],pending))
    example_evidence=load('fixtures/evidence-example.json')
    check('Example evidence is explicitly not live proof', example_evidence['proof_status']=='MOCK_ONLY' and example_evidence['provider_mode']=='MOCK' and example_evidence['vendor_decision_reference'] is None)

    products={p['sku']:p for p in load('fixtures/catalog.json')['products']}
    gross=sum(Decimal(products[r['sku']]['unit_price'])*r['quantity'] for r in base['items'])
    expectations=load('fixtures/pricing-expectations.json')
    check('Fixture basket gross is accurate',gross==Decimal(expectations['merchandise_subtotal']))
    for case in expectations['cases']:
        discount=(gross*Decimal(case['bps'])/Decimal(10000)).quantize(Decimal('0.01'))
        check(f'Fixture arithmetic at {case["bps"]} bps',discount==Decimal(case['discount']) and gross-discount==Decimal(case['net_merchandise']))

    api=yaml.safe_load((ROOT/'contracts/openapi.yaml').read_text())
    refs=list(walk_refs(api))
    check('OpenAPI internal references resolve',all(pointer(api,r) for r in refs),f'{len(refs)} references; not a full external OpenAPI validator.')
    op_ids=[]
    for path,item in api['paths'].items():
        for method,operation in item.items():
            if method not in ['get','post','put','delete','patch','options','head']: continue
            op_ids.append(operation.get('operationId'))
            params=item.get('parameters',[])+operation.get('parameters',[])
            names={p.get('name') for p in params if p.get('in')=='path' and p.get('required')}
            check(f'OpenAPI path parameters: {method.upper()} {path}',set(re.findall(r'\{([^}]+)\}',path))==names)
    check('OpenAPI operation IDs unique and populated',None not in op_ids and len(op_ids)==len(set(op_ids)))

    for p in (ROOT/'contracts').glob('*.schema.sql'):
        try:
            with sqlite3.connect(':memory:') as conn:
                conn.executescript(p.read_text())
                conn.executescript(p.read_text())
                tables=conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            check(f'SQLite DDL executes twice: {p.name}',True,f'{len(tables)} tables; no application transactions tested.')
        except Exception as exc:
            check(f'SQLite DDL executes twice: {p.name}',False,str(exc))

    missing=[]
    for p in [p for p in files if p.suffix=='.md']:
        text=p.read_text()
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=raw.split('#',1)[0].split('?',1)[0]
            if not target or re.match(r'^[a-zA-Z]+:',target) or '<' in target: continue
            if not (p.parent/target).exists(): missing.append(f'{p.relative_to(ROOT)} -> {target}')
    check('Local Markdown links resolve',not missing,'; '.join(missing[:20]))
    check('Root AGENTS.md under 32 KiB', (ROOT/'AGENTS.md').stat().st_size<32768)
    sources=load('config/source-register.json')['sources']
    check('Source IDs unique and HTTPS',len({s['id'] for s in sources})==len(sources) and all(s['url'].startswith('https://') for s in sources))
    sensitive_nonempty=[]
    for p in (ROOT/'config').glob('*.env.example'):
        for line in p.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line: continue
            key,value=line.split('=',1)
            if re.search(r'(SECRET|TOKEN|CREDENTIAL|SIGNING_KEY|CONTEXT_KEY|API_KEY)$',key) and value.strip(): sensitive_nonempty.append(f'{p.name}:{key}')
    check('Credential example values blank', not sensitive_nonempty,', '.join(sensitive_nonempty))
    for p in (ROOT/'graphql').glob('*.graphql'):
        text='\n'.join(line for line in p.read_text().splitlines() if not line.strip().startswith('#'))
        check(f'GraphQL delimiter check: {p.name}',text.count('{')==text.count('}') and text.count('(')==text.count(')'), 'Structural check only; syntax and pinned provider schema must be validated live.')
    for name in ['create_quote.graphql','get_quote.graphql']:
        text=(ROOT/'graphql'/name).read_text()
        check(f'Actual-price and readiness selections: {name}', all(v in text for v in ['ready','originalUnitPriceSet','totalPriceSet']))
    variables=load('graphql/create_quote.variables.example.json')['input']
    check('No stacked discounts in example mutation',variables['acceptAutomaticDiscounts'] is False and variables['allowDiscountCodesInCheckout'] is False and variables['discountCodes']==[])
    ids=re.findall(r'\|\s*(T\d+)\s*\|',(ROOT/'docs/10_TESTS_AND_PROOF.md').read_text())
    check('Test-case identifiers unique',len(ids)==len(set(ids)))
    check('At least 50 future application test cases specified',len(ids)>=50,f'{len(ids)} specified tests, NOT executed application tests.')

    failed=[r for r in RESULTS if not r['passed']]
    report={'artifact':'CounterOffer implementation handoff','scope':'Offline documentation and contract integrity only','checks_total':len(RESULTS),'checks_passed':len(RESULTS)-len(failed),'checks_failed':len(failed),'future_application_test_cases_specified':len(ids),'not_executed':['Application implementation/unit tests','Actual AgntID runtime enforcement','Bedrock inference','Shopify authentication or mutation','Docker deployment or ARM64 runtime test','Phone/tunnel end-to-end tests','Live GraphQL schema validation'],'results':RESULTS}
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'Documentation checks: {report["checks_passed"]}/{len(RESULTS)} passed')
    print(f'Future application test cases specified: {len(ids)} (not executed)')
    for item in failed: print(f'FAIL: {item["check"]}: {item["detail"]}')
    print('No external connections or application acceptance tests were executed.')
    return 1 if failed else 0

if __name__=='__main__':
    sys.exit(main())
