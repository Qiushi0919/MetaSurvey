import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { estimateCost, affordableQty, parseCents, roundYuanToCents } from '../src/baseline/economics.mjs';

const fixture = JSON.parse(await readFile(new URL('./fixtures/synthetic/economics.json', import.meta.url), 'utf8'));
const config = fixture.cost_config;
const trade_date = fixture.trade_date;
const expectCode = (code, run) => assert.throws(run, error => error.code === code);

// Test oracle uses rational BigInt arithmetic, not Decimal or the estimator under audit.
function fraction(text) {
  const [whole, tail = ''] = text.split('.');
  return [BigInt(whole + tail), 10n ** BigInt(tail.length)];
}
function roundedFraction(numerator, denominator) {
  return (2n * numerator + denominator) / (2n * denominator);
}
function oracle(price, quantity, side, profile) {
  const [priceN, priceD] = fraction(price);
  const amountN = priceN * BigInt(quantity);
  const gross = roundedFraction(amountN * 100n, priceD);
  function fee(rate) {
    const [rateN, rateD] = fraction(rate);
    return roundedFraction(amountN * rateN * 100n, priceD * rateD);
  }
  const minimum = BigInt(profile.minimum_commission_cents);
  const commission = fee(profile.commission_rate) > minimum ? fee(profile.commission_rate) : minimum;
  const exchange = profile.exchange_fee_included ? 0n : fee(profile.exchange_fee_rate);
  const other = profile.other_fee_included ? 0n : fee(profile.other_fee_rate);
  const stamp = side === 'SELL' ? fee(profile.stamp_tax_sell_rate) : 0n;
  const total = commission + exchange + other + stamp;
  return { gross, commission, exchange, other, stamp, total, delta: side === 'BUY' ? -(gross + total) : gross - total };
}

test('synthetic fee schedule is explicit and cannot claim production provenance', () => {
  assert.equal(fixture.provenance, 'SYNTHETIC_NOT_PRODUCTION');
  expectCode('BASELINE_CONFIG_ONLY', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date, config: { ...config, provenance: 'PRODUCTION_VERIFIED' } }));
});

test('Decimal HALF_UP cents match independent integer boundary values and negative rounding', () => {
  for (const [yuan, cents] of [['0.004999', '0'], ['0.005', '1'], ['0.005001', '1'], ['-0.005', '-1'], ['-0.004999', '0'], ['100000000000000.01', '10000000000000001']]) {
    assert.equal(roundYuanToCents(yuan), cents);
  }
});

test('commission floor below / exactly / above boundary uses explicit synthetic PER_ORDER config', () => {
  for (const [price, expected] of [['13.5', '137'], ['13.7', '137'], ['13.8', '138']]) {
    const result = estimateCost({ price, quantity: 100, side: 'BUY', trade_date, config });
    assert.equal(result.components_cents.commission, expected);
    assert.equal(result.commission_scope, 'PER_ORDER');
  }
});

test('exact notional rounds once, then explicit components round individually', () => {
  for (const price of ['1.005', '1.337', '17.325', '13.7', '0.005', '100000000000000.01']) {
    for (const quantity of [1, 101, 300]) {
      for (const side of ['BUY', 'SELL']) {
        const expected = oracle(price, quantity, side, config);
        const result = estimateCost({ price, quantity, side, trade_date, config });
        assert.equal(result.gross_notional_cents, expected.gross.toString());
        for (const component of ['commission', 'exchange', 'other', 'stamp']) assert.equal(result.components_cents[component], expected[component].toString());
        assert.equal(result.explicit_fees_cents, expected.total.toString());
        assert.equal(result.cash_delta_cents, expected.delta.toString());
      }
    }
  }
});

test('fee-inclusive affordability blocks one lot even when its bare notional fits', () => {
  const request = { ...fixture.affordability, trade_date, config };
  assert.equal(affordableQty(request), fixture.affordability.expected_quantity);
  assert.equal(affordableQty({ ...request, budget_cents: '122500' }), 0);
  assert.equal(affordableQty({ ...request, budget_cents: '122639' }), 0);
  assert.equal(affordableQty({ ...request, budget_cents: '0' }), 0);
  assert.equal(affordableQty({ ...request, budget_cents: '99999999', max_quantity: 199 }), 100);
});

test('included exchange/other fees and price-embedded slippage cannot be charged twice', () => {
  const inclusive = { ...config, exchange_fee_included: true, other_fee_included: true };
  const result = estimateCost({ price: '17.325', quantity: 300, side: 'BUY', trade_date, config: inclusive });
  assert.equal(result.gross_notional_cents, '519750');
  assert.equal(result.components_cents.exchange, '0');
  assert.equal(result.components_cents.other, '0');
  assert.equal(result.all_in_buy_cents, '520270');
  expectCode('SLIPPAGE_DOUBLE_COUNT_OR_UNRESOLVED', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date, config: { ...config, slippage_treatment: 'CHARGE_AGAIN' } }));
});

test('every missing or UNSET_REQUIRED fee field blocks estimates, including included fee rates', () => {
  for (const field of Object.keys(config)) {
    expectCode('UNSET_REQUIRED', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date, config: { ...config, [field]: 'UNSET_REQUIRED' } }));
    const missing = { ...config };
    delete missing[field];
    expectCode('UNSET_REQUIRED', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date, config: missing }));
  }
});

test('cost model effective interval is from-inclusive to-exclusive', () => {
  expectCode('COST_VERSION_NOT_EFFECTIVE', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date: '2025-12-31', config }));
  expectCode('COST_VERSION_NOT_EFFECTIVE', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date: '2027-01-01', config }));
  assert.equal(estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date: '2026-01-01', config }).cost_model_version, config.version);
});

test('canonical decimal / integer money and 38-digit bounds reject unsafe or ambiguous wire values', () => {
  for (const value of [137, '01', '+1', '-0', '1.0', '1e3', '9'.repeat(39)]) expectCode('INVALID_MONEY', () => parseCents(value));
  assert.equal(parseCents('9'.repeat(38)), BigInt('9'.repeat(38)));
  for (const price of [12.25, '01', '1e2', '1.0', '0', '1.1234567']) assert.throws(() => estimateCost({ price, quantity: 1, side: 'BUY', trade_date, config }));
  assert.throws(() => estimateCost({ price: '1', quantity: Number.MAX_SAFE_INTEGER + 1, side: 'BUY', trade_date, config }));
  expectCode('INVALID_MONEY', () => estimateCost({ price: '9'.repeat(38), quantity: 1, side: 'BUY', trade_date, config }));
  expectCode('DECIMAL_PRECISION_EXCEEDED', () => estimateCost({ price: '1', quantity: 1, side: 'BUY', trade_date, config: { ...config, commission_rate: '0.00000000001' } }));
});
