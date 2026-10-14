"""Bounded current-document factor extraction; no market, credentials or history.

All economic numbers are extracted from pinned local originals, never test defaults.
The former V1 financial scores and all previous files are read-only.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path
import argparse, hashlib, json, re

ROOT = Path(__file__).resolve().parents[2]
OLD = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-pilot-v1-20261014/data')
OUT = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014/research')
METHOD = 'experiments/e2e_history_v2/research-method.json'
NUMBER = r'([0-9][0-9,]*(?:\.[0-9]+)?)'
BUSINESS = {'603228': (21, '印制电路板'), '002463': (20, '印制电路板'),
            '002916': (16, '印制电路板'), '600312': (17, '高压板块')}
CUSTOMER = {'603228': (23, 'TOP5_UPPER_BOUND'), '002463': (22, 'REPORTED_LARGEST'),
            '002916': (18, 'REPORTED_LARGEST'), '600312': (19, 'REPORTED_LARGEST'),
            '601179': (17, 'EXPLICIT_NO_ABOVE'), '002028': (19, 'REPORTED_LARGEST'),
            '600362': (21, 'TOP5_UPPER_BOUND')}
AUDIT = {'603228': 85, '002463': 80, '002916': 81, '600312': 64,
         '601179': 60, '002028': 69, '601899': 2, '600362': 94}


def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
def seal(value): return digest(canonical({k: v for k, v in value.items() if k != 'content_hash'}))
def exact(value):
    if type(value) is not str or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('DECIMAL_STRING_REQUIRED')
    return Decimal(value)


def business_result(fact):
    if fact['state'] != 'VERIFIED_COMPATIBLE_REPORTED_SEGMENT':
        return {'state': 'UNKNOWN', 'share': None, 'exposure_subfactor': None,
                'reason': fact['reason'], 'complete_sector_benefit_score': None}
    if (fact['unit'] != 'CNY' or fact['denominator']['unit'] != 'CNY'
            or fact['period'] != fact['denominator']['period']
            or fact['period'] != 'FY2025' or not fact['external_revenue_compatible']):
        raise ValueError('INCOMPATIBLE_BUSINESS_SCOPE')
    with localcontext() as ctx:
        ctx.prec = 40; ctx.rounding = ROUND_HALF_EVEN
        numerator, denominator = exact(fact['numerator']), exact(fact['denominator']['value'])
        if denominator <= 0 or not 0 <= numerator <= denominator:
            raise ValueError('BUSINESS_SHARE_OUT_OF_RANGE')
        share = numerator / denominator
        return {'state': 'COMPUTED_CURRENT_OBSERVED', 'share': format(share, 'f'),
                'exposure_subfactor': format((share * 100).quantize(Decimal('.0001')), 'f'),
                'complete_sector_benefit_score': None,
                'reason': 'DISCLOSED_REVENUE_EXPOSURE_NOT_UPSIDE_PROBABILITY'}


def concentration_result(fact):
    state = fact['state']
    if state == 'UNKNOWN':
        return {'state': 'UNKNOWN', 'deduction': None, 'largest_share': None, 'reason': fact['reason']}
    if state == 'EXPLICIT_NO_ABOVE':
        if fact.get('explicit_no_above') is not True: raise ValueError('DIRECT_STATEMENT_REQUIRED')
        return {'state': 'NOT_ABOVE_THRESHOLD_REPORTED', 'deduction': '0',
                'largest_share': None, 'reason': 'DIRECT_ISSUER_STATEMENT_NO_SINGLE_CUSTOMER_ABOVE_50_PERCENT'}
    if state not in ('REPORTED_LARGEST', 'TOP5_UPPER_BOUND'):
        raise ValueError('UNKNOWN_CONCENTRATION_EVIDENCE_KIND')
    percent = exact(fact['reported_percent'])
    if not 0 <= percent <= 100: raise ValueError('INVALID_CUSTOMER_PERCENT')
    # Percentages rounded in annual reports cannot prove a strict threshold at 50.00.
    lower, upper = max(Decimal(0), percent - Decimal('.005')), min(Decimal(100), percent + Decimal('.005'))
    above = state == 'REPORTED_LARGEST' and lower > 50
    below = upper <= 50
    known = above or below
    return {'state': 'ABOVE_THRESHOLD_REPORTED' if above else 'NOT_ABOVE_THRESHOLD_REPORTED' if below else 'UNKNOWN',
            'deduction': '10' if above else '0' if below else None,
            'largest_share': format(percent / 100, 'f') if state == 'REPORTED_LARGEST' else None,
            'largest_share_exact': False,
            'reported_basis': fact['basis'],
            'reason': ('TOP5_BOUND_NOT_LARGEST_VALUE' if state == 'TOP5_UPPER_BOUND' and known
                       else 'ROUNDED_REPORTED_PERCENT_THRESHOLD' if known else 'ROUNDED_OR_TOP5_BOUND_CANNOT_RESOLVE_50_PERCENT')}


def evaluate(pack):
    if (pack.get('kind') != 'E2ENewResearchFactorInputs' or pack.get('version') != '1.0.0'
            or pack.get('historical_visibility_proven') is not False
            or pack.get('productionGate') is not False): raise ValueError('INPUT_SCOPE')
    if datetime.fromisoformat(pack['recorded_at']) < datetime.fromisoformat(pack['method_frozen_at']):
        raise ValueError('METHOD_NOT_FROZEN')
    rows = []
    for company in pack['companies']:
        rows.append({'symbol': company['symbol'], 'name': company['name'],
                     'business_exposure': business_result(company['business']),
                     'customer_concentration': concentration_result(company['concentration']),
                     'audit_opinion': company['audit_opinion'],
                     'leverage_risk': 'UNKNOWN', 'litigation_and_other_risk': 'UNKNOWN',
                     'catalyst': 'NOT_ASSESSED_NO_COMPLETE_60_SESSION_SEARCH',
                     'complete_seven_factor_score': None})
    result = {'kind': 'E2ENewResearchFactors', 'version': '1.0.0', 'recorded_at': pack['recorded_at'],
              'method_hash': pack['method_hash'], 'input_hash': seal(pack),
              'result_type': 'CURRENT_OBSERVED_EXPERIMENTAL_RESEARCH', 'companies': rows,
              'historical_visibility_proven': False, 'productionGate': False,
              'prior_27_factors_modified': False, 'independent_human_review': False}
    result['content_hash'] = seal(result)
    return result


def prepare():
    from pypdf import PdfReader
    old_path = OLD / 'Financial-Inputs.json'
    old = json.loads(old_path.read_text())
    method_raw = (ROOT / METHOD).read_bytes(); method = json.loads(method_raw)
    freeze = json.loads((ROOT / 'docs/e2e-history-v2/Freeze.json').read_text())
    if freeze['files'][METHOD] != digest(method_raw): raise ValueError('FROZEN_METHOD_MISMATCH')
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for co in old['companies']:
        symbol = co['symbol'][:6]
        source = next(s for s in old['sources'] if s['symbol'] == symbol)
        path = OLD / (symbol + '-2025.pdf')
        if path.resolve() != path or path.is_symlink(): raise ValueError('UNSAFE_ORIGINAL')
        if digest(path.read_bytes()) != 'sha256:' + source['sha256']: raise ValueError('ORIGINAL_HASH_MISMATCH')
        reader = PdfReader(path)

        def page(number): return reader.pages[number - 1].extract_text() or ''
        def proof(number, label):
            text = page(number)
            return {'source_id': source['source_id'], 'source_sha256': 'sha256:' + source['sha256'],
                    'path': str(path), 'page': number, 'page_text_sha256': digest(text.encode()),
                    'location': label, 'period': 'FY2025', 'published_at': None,
                    'retrieved_at': source['retrieved_at'], 'available_at': source['available_at'],
                    'extraction_observed_at': now, 'historical_visibility_proven': False}
        business = {'state': 'UNKNOWN', 'reason': 'NO_COMPATIBLE_EXTERNAL_SEGMENT_REVENUE',
                    'score': None, 'denominator': co['facts']['revenue']}
        if symbol in BUSINESS:
            number, label = BUSINESS[symbol]
            text = re.sub(r'\s+', ' ', page(number))
            hit = re.search(r'\s*'.join(map(re.escape, label)) + r'\s+' + NUMBER, text)
            if not hit: raise ValueError('SEGMENT_ROW_MISSING_' + symbol)
            business.update(state='VERIFIED_COMPATIBLE_REPORTED_SEGMENT', numerator=hit[1].replace(',', ''),
                            unit='CNY', period='FY2025', external_revenue_compatible=True,
                            numerator_definition=label + '销售收入，非产品成本/其他业务/封装与装联',
                            formula='reported compatible segment revenue / consolidated FY2025 revenue',
                            source=proof(number, '收入构成/主营业务分产品表：' + label),
                            reason='EXACT_NARROW_DISCLOSED_BUSINESS_CATEGORY')
        elif symbol in ('601179', '002028'):
            number = 14 if symbol == '601179' else 17
            business.update(reason='MIXED_VOLTAGE_SWITCH_TRANSFORMER_REVENUE_NOT_EXPLICIT_HIGH_VOLTAGE',
                            source=proof(number, '分产品：开关、变压器；未单独拆高压收入'))
        elif symbol == '600362':
            text = re.sub(r'\s+', ' ', page(18))
            known = []
            for label in ('阴极铜', '铜杆线', '铜加工产品'):
                hit = re.search(r'\s*'.join(map(re.escape, label)) + r'\s+' + NUMBER, text)
                if not hit: raise ValueError('COPPER_ROW_MISSING')
                known.append({'label': label, 'value': hit[1].replace(',', ''), 'unit': 'CNY'})
            business.update(reason='COPPER_MIXED_OTHER_NONFERROUS_ROW_NOT_SPLIT;KNOWN_COPPER_ROWS_LOWER_BOUND_ONLY',
                            known_copper_revenue_components=known,
                            lower_bound_not_full_share=True, source=proof(18, '阴极铜、铜杆线、铜加工产品；含贸易'),
                            scope_source=proof(19, '铜精矿、稀散及其他有色金属混合行；全部产品含贸易'))
        elif symbol == '601899':
            business.update(reason='SEVEN_PAGE_ANNUAL_SUMMARY_HAS_NO_SEGMENT_REVENUE',
                            source=proof(2, '年度报告摘要，业务简介不能代替收入表'))
        else:
            business.update(reason='PDF_SEGMENT_LABELS_UNREADABLE_AND_INTERNAL_ELIMINATIONS_UNALLOCATED',
                            source=proof(33, '分产品表内部交易抵销未分配'))

        concentration = {'state': 'UNKNOWN', 'reason': 'NO_VERIFIED_CUSTOMER_SALES_TABLE'}
        if symbol in CUSTOMER:
            number, mode = CUSTOMER[symbol]
            raw = page(number); text = re.sub(r'\s+', ' ', raw)
            concentration.update(state=mode, basis='AS_REPORTED_ANNUAL_SALES_CUSTOMER_GROUPING;NOT_RECAST_TO_NEW_GROUP',
                                 source=proof(number, '主要销售客户；原报告客户归并及年度销售总额口径'))
            if mode == 'TOP5_UPPER_BOUND':
                hit = re.search(r'前五名客户销售额.*?占年度销售总额\s*' + NUMBER + r'%', text)
            elif mode == 'REPORTED_LARGEST':
                label = '国家电网有限公司及其所属公司' if symbol == '600312' else '第一名' if symbol == '002916' else '客户一'
                hit = re.search(r'1\s*' + re.escape(label) + r'\s*' + NUMBER + r'\s+' + NUMBER, text)
            else:
                compact = re.sub(r'\s+', '', raw)
                if '不存在向单个客户的销售比例超过总额的50%' not in compact: raise ValueError('EXPLICIT_NEGATION_MISSING')
                concentration['explicit_no_above'] = True; hit = None
            if mode != 'EXPLICIT_NO_ABOVE':
                if not hit: raise ValueError('CUSTOMER_ROW_MISSING_' + symbol)
                concentration['reported_percent'] = hit[2] if mode == 'REPORTED_LARGEST' else hit[1]
            if symbol == '002463': concentration['basis_limitation'] = 'delivery-recipient grouping; terminal-customer largest ratio not disclosed'
        else:
            concentration['reason'] = ('ANNUAL_SUMMARY_HAS_NO_CUSTOMER_TABLE' if symbol == '601899'
                                       else 'CUSTOMER_LABELS_UNREADABLE;RECEIVABLE_CONCENTRATION_IS_NOT_SALES_CONCENTRATION')
        audit = {'state': 'UNKNOWN', 'reason': 'UNVERIFIED_AUDIT_OPINION_TEXT'}
        if symbol in AUDIT:
            number = AUDIT[symbol]; text = re.sub(r'\s+', '', page(number))
            if symbol == '601899':
                if '标准无保留意见' not in text: raise ValueError('SUMMARY_AUDIT_TEXT_MISSING')
                status = 'ISSUER_SUMMARY_REPORTS_UNQUALIFIED_OPINION'
            else:
                if '公允反映' not in text or '审计意见' not in text: raise ValueError('AUDIT_TEXT_MISSING')
                status = 'UNQUALIFIED_OPINION_TEXT_OBSERVED'
            audit = {'state': status, 'source': proof(number, '审计意见/摘要重要提示'),
                     'does_not_clear': ['leverage', 'litigation', 'thesis_invalidation', 'later_revisions']}
        records.append({'symbol': co['symbol'], 'name': co.get('name', co['symbol']),
                        'sector': co['sector'], 'business': business,
                        'concentration': concentration, 'audit_opinion': audit})
    pack = {'kind': 'E2ENewResearchFactorInputs', 'version': '1.0.0', 'recorded_at': now,
            'method_hash': digest(method_raw), 'method_frozen_at': method['frozen_at'],
            'prior_inputs_path': str(old_path), 'prior_inputs_hash': digest(old_path.read_bytes()),
            'input_schema': {'numbers': 'Decimal strings', 'period': 'FY2025', 'money_unit': 'CNY',
                             'percent_unit': 'PERCENT_POINTS', 'clock': 'CURRENT_OBSERVED_ONLY'},
            'source_files': [{'path': s['path'], 'sha256': 'sha256:' + s['sha256'], 'bytes': s['bytes']} for s in old['sources']],
            'companies': records, 'productionGate': False, 'historical_visibility_proven': False}
    pack['content_hash'] = seal(pack)
    return pack


def independent_recompute(pack, result):
    rows = []
    for original, row in zip(pack['companies'], result['companies'], strict=True):
        b = original['business']
        value = None
        if b['state'] == 'VERIFIED_COMPATIBLE_REPORTED_SEGMENT':
            ratio = Fraction(b['numerator']) / Fraction(b['denominator']['value'])
            actual = Fraction(row['business_exposure']['share'])
            if abs(ratio - actual) > Fraction(1, 10**38): raise ValueError('INDEPENDENT_SHARE_MISMATCH')
            value = str(ratio)
        c = original['concentration']; mode = c['state']; deduction = None
        if mode == 'EXPLICIT_NO_ABOVE' and c.get('explicit_no_above') is True:
            deduction = '0'
        elif mode in ('REPORTED_LARGEST', 'TOP5_UPPER_BOUND'):
            percent = Fraction(c['reported_percent']); uncertainty = Fraction(1, 200)
            if mode == 'REPORTED_LARGEST' and percent - uncertainty > 50: deduction = '10'
            elif percent + uncertainty <= 50: deduction = '0'
        if row['customer_concentration']['deduction'] != deduction:
            raise ValueError('INDEPENDENT_CUSTOMER_PREDICATE_MISMATCH')
        rows.append({'symbol': original['symbol'], 'business_share_exact_fraction': value,
                     'customer_deduction_independent': deduction})
    return {'kind': 'ResearchFactorFractionRecompute', 'input_hash': seal(pack),
            'result_hash': result['content_hash'], 'companies': rows,
            'independent_human_review': False, 'implementation': 'fractions.Fraction independent ratio arithmetic'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--produce', action='store_true'); args = parser.parse_args()
    if not args.produce: parser.error('--produce required; writes only new fixed private results')
    OUT.mkdir(parents=True, exist_ok=True)
    pack = prepare(); result = evaluate(pack); arithmetic = independent_recompute(pack, result)
    outputs = {'Research-Factor-Inputs.json': pack, 'Research-Factors.json': result, 'Independent-Recompute.json': arithmetic}
    if any((OUT / name).exists() for name in outputs): raise ValueError('NO_OVERWRITE_EXISTING_OUTPUTS')
    for name, value in outputs.items():
        with (OUT / name).open('x') as stream: json.dump(value, stream, ensure_ascii=False, indent=2)
        (OUT / name).chmod(0o600)
    print(json.dumps({'companies': len(result['companies']),
                      'new_business_subfactors': sum(r['business_exposure']['exposure_subfactor'] is not None for r in result['companies']),
                      'known_customer_predicates': sum(r['customer_concentration']['deduction'] is not None for r in result['companies']),
                      'full_scores': 0, 'historical_inputs': False}))


if __name__ == '__main__': main()
