"""Offline, exact-arithmetic review of the bounded public-disclosure input pack.

No network or credential access. Original PDFs and numeric output stay outside Git.
Requires pypdf from the local document runtime; this is not a market-data collector.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-pilot-v1-20261014/data')
FIELDS = ('revenue', 'prior_revenue', 'net_profit', 'operating_cashflow')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.resolve().parent != ARCHIVE.resolve():
        raise ValueError('OUTSIDE_FIXED_ARCHIVE_OR_SYMLINK')
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('OVERSIZE_INPUT')
    return path


def exact(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('NOT_DECIMAL_STRING')
    return Fraction(value)


def audit(input_path, method_path):
    from pypdf import PdfReader
    path = bounded(input_path)
    pack = json.loads(path.read_text())
    method = json.loads(Path(method_path).read_text())
    if pack['method_sha256'] != sha(Path(method_path)):
        raise ValueError('METHOD_HASH_MISMATCH')
    if pack['namespace'] != 'EXPERIMENT:CORE40:E2E_PILOT_V1' or not pack['not_historical_pit']:
        raise ValueError('NAMESPACE_OR_PIT_SCOPE_MISMATCH')
    if pack['productionGate'] is not False:
        raise ValueError('PRODUCTION_FORBIDDEN')
    sources = {row['source_id']: row for row in pack['sources']}
    if len(sources) != 9 or len(pack['companies']) != 9:
        raise ValueError('FIXED_NINE_REQUIRED')
    readers = {}
    for sid, source in sources.items():
        pdf = bounded(source['path'])
        if sha(pdf) != source['sha256'] or pdf.stat().st_size != source['bytes']:
            raise ValueError('RAW_HASH_OR_SIZE_MISMATCH')
        if not pdf.read_bytes().startswith(b'%PDF-'):
            raise ValueError('INVALID_PDF')
        if source['historical_visibility_proven'] is not False:
            raise ValueError('HISTORICAL_CLOCK_CLAIM_FORBIDDEN')
        readers[sid] = PdfReader(pdf)
    expected = {member['symbol']: sector['id'] for sector in method['universe'] for member in sector['members']}
    actual = {row['symbol']: row['sector'] for row in pack['companies']}
    if expected != actual or len(actual) != len(pack['companies']):
        raise ValueError('UNIVERSE_MISMATCH_OR_DUPLICATE')
    rows = []
    for company in pack['companies']:
        values = {}
        for name in FIELDS:
            fact = company['facts'][name]
            if fact['unit'] != 'CNY' or fact['consolidation'] != 'CONSOLIDATED_GROUP':
                raise ValueError('UNIT_OR_CONSOLIDATION_MISMATCH')
            period = 'FY2024' if name == 'prior_revenue' else 'FY2025'
            if fact['period'] != period:
                raise ValueError('PERIOD_MISMATCH')
            if fact['source_id'] != 'official-fy2025:' + company['symbol'][:6]:
                raise ValueError('CROSS_ISSUER_FACT')
            source = sources[fact['source_id']]
            if fact['available_at'] != source['retrieved_at'] or fact['retrieved_at'] != source['retrieved_at'] or fact['published_at'] is not None or fact['historical_visibility_proven'] is not False:
                raise ValueError('CLOCK_MISMATCH')
            if fact['revision_version'] != source['sha256']:
                raise ValueError('REVISION_MISMATCH')
            page = fact['page']
            if not isinstance(page, int) or not 1 <= page <= len(readers[fact['source_id']].pages):
                raise ValueError('PAGE_INVALID')
            text = readers[fact['source_id']].pages[page - 1].extract_text()
            compact = re.sub(r'[\s,]', '', text)
            for component in fact['source_components']:
                exact(component)
                if component not in compact and not (component.startswith('-') and '(' + component[1:] in compact):
                    raise ValueError('SOURCE_NUMERIC_LITERAL_NOT_FOUND')
            value = exact(fact['value'])
            if fact['calculation'] == 'SUM_FOUR_REPORTED_QUARTERS':
                if len(fact['source_components']) != 4 or sum(map(exact, fact['source_components'])) != value:
                    raise ValueError('QUARTER_SUM_MISMATCH')
            elif fact['calculation'] != 'IDENTITY_CNY_NO_SCALING' or fact['source_components'] != [fact['value']]:
                raise ValueError('UNKNOWN_CONVERSION')
            values[name] = value
        revenue, prior, profit, cfo = (values[k] for k in FIELDS)
        if revenue <= 0 or prior <= 0 or profit <= 0:
            raise ValueError('FINANCIAL_DENOMINATOR_NOT_POSITIVE')
        ratios = {'revenue_growth': revenue / prior - 1, 'cash_conversion': cfo / profit, 'net_margin': profit / revenue}
        scores = {}
        for name, value in ratios.items():
            low, high = map(exact, method['anchors'][name])
            scores[name] = 100 * min(Fraction(1), max(Fraction(0), (value - low) / (high - low)))
        rows.append({'symbol': company['symbol'], 'sector': company['sector'], 'ratios_exact': {k: str(v) for k, v in ratios.items()}, 'component_scores_exact': {k: str(v) for k, v in scores.items()}, 'financial_subtotal_exact': str(sum(scores.values()) / 3), 'full_score': None})
    sectors = []
    for sector in method['universe']:
        selected = [row for row in rows if row['sector'] == sector['id']]
        if len(selected) != 3:
            raise ValueError('INCOMPLETE_SECTOR')
        sectors.append({'sector': sector['id'], 'members': [r['symbol'] for r in selected], 'financial_proxy_subtotal_exact': str(sum(Fraction(r['financial_subtotal_exact']) for r in selected) / 3), 'risk_screened_total': None})
    return {'kind': 'IndependentFractionArithmeticReview', 'version': '1.0.0', 'recorded_at': datetime.now(timezone.utc).isoformat(), 'input_sha256': sha(path), 'method_sha256': sha(Path(method_path)), 'auditor_code_sha256': sha(Path(__file__)), 'original_pdf_hashes_checked': len(readers), 'financial_facts_checked': len(rows) * 4, 'source_literal_check_limit': 'Checks exact numeric presence on specified page; semantic row/column selection also needs issuer-table inspection.', 'arithmetic_implementation': 'fractions.Fraction; separate from Decimal production scorer', 'independent_human_review': False, 'productionGate': False, 'historical_visibility_proven': False, 'companies': rows, 'sectors': sectors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ARCHIVE / 'Financial-Inputs.json')
    parser.add_argument('--method', type=Path, default=Path(__file__).resolve().parents[2] / 'experiments/e2e_pilot_v1/method.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().parent != ARCHIVE.resolve() or args.output.exists():
        raise ValueError('OUTPUT_MUST_BE_NEW_FIXED_PRIVATE_ARCHIVE_FILE')
    result = audit(args.input, args.method)
    with args.output.open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    args.output.chmod(0o600)
    print(json.dumps({'original_pdf_hashes_checked': result['original_pdf_hashes_checked'], 'financial_facts_checked': result['financial_facts_checked'], 'output_sha256': sha(args.output), 'historical_visibility_proven': False}))


if __name__ == '__main__':
    main()
