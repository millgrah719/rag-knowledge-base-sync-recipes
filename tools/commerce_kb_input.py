#!/usr/bin/env python3
"""Offline adapter: Variant Ledger normalization result to Apify inline input.
No requests, credentials, charges, or automatic indexing.
"""
import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = ('name', 'brand', 'color', 'size', 'material', 'pattern', 'gtin', 'mpn')


def convert(result, corpus):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', corpus):
        raise ValueError('Invalid corpus ID')
    if not isinstance(result, dict) or not isinstance(result.get('schema_version'), str):
        raise ValueError('Expected a Variant Ledger normalization result')
    diagnostics = result.get('diagnostics')
    if not isinstance(diagnostics, list) or any(not isinstance(d, dict) or d.get('severity') != 'info' for d in diagnostics):
        raise ValueError('Review all normalization warnings/errors before indexing')
    products = result.get('products')
    if not isinstance(products, list) or not 1 <= len(products) <= 500:
        raise ValueError('Expected 1–500 products')
    rows, seen = [], set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError('Invalid product')
        field = product.get('sku')
        sku = field.get('value') if isinstance(field, dict) else None
        if not isinstance(sku, str) or not sku or sku != sku.strip() or any(ord(c) < 32 for c in sku):
            raise ValueError('Every product requires a stable, clean string SKU')
        if sku in seen:
            raise ValueError('Duplicate SKU: resolve before creating the knowledge base')
        seen.add(sku)
        lines = ['Product SKU: ' + sku]
        for name in FIELDS:
            field = product.get(name)
            value = field.get('value') if isinstance(field, dict) else None
            if isinstance(value, str) and value.strip():
                lines.append(name.title() + ': ' + ' '.join(value.split()))
        if len(lines) == 1:
            raise ValueError('A product has no supported descriptive attributes')
        content = '\n'.join(lines)
        if len(content) > 120000:
            raise ValueError('Product record exceeds the text limit')
        rows.append({'sku': sku, 'text': content})
    rows.sort(key=lambda row: row['sku'])
    if sum(len(row['text'].encode('utf-8')) for row in rows) > 6000000:
        raise ValueError('Combined text exceeds 6 MB')
    return {'inputMode': 'inline', 'records': rows, 'corpusId': corpus,
            'sourceField': 'sku', 'textField': 'text', 'completeSnapshot': False}


def self_test():
    field = lambda value: {'value': value, 'source': {'document_id': 'demo', 'pointer': '/demo'}, 'inherited': False}
    product = {'sku': field('DEMO-BLUE-M'), 'name': field('Demo shirt'),
               'color': field('Blue'), 'size': field('M'),
               'offers': [{'price': field('29.99'), 'availability': field('in_stock')}]}
    result = {'schema_version': 'demo', 'products': [product], 'diagnostics': [], 'summary': {}}
    out = convert(result, 'demo')
    assert out['completeSnapshot'] is False and out['sourceField'] == 'sku'
    assert out['records'][0]['sku'] == 'DEMO-BLUE-M'
    assert '29.99' not in out['records'][0]['text'] and 'in_stock' not in out['records'][0]['text']
    for bad in [dict(result, products=[product, product]),
                dict(result, diagnostics=[{'severity': 'warning'}]),
                dict(result, products=[]),
                dict(result, products=[{'name': field('No SKU')}])]:
        try:
            convert(bad, 'demo')
        except ValueError:
            pass
        else:
            raise AssertionError('Expected invalid data to be rejected')
    print('Offline checks passed: stable SKU, no volatile offers, partial snapshot, duplicate, warning, empty input, missing SKU.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', nargs='?', type=Path, help='Saved normalization result JSON')
    parser.add_argument('--corpus-id', default='catalog-support')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.result is None:
        parser.error('Provide a saved result or use --self-test')
    try:
        with args.result.open(encoding='utf-8') as f:
            result = json.load(f)
        print(json.dumps(convert(result, args.corpus_id), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        print('Conversion stopped: ' + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
