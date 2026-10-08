"""Synthetic-only adversarial and independently calculated diagnostic checks."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
import unittest

from wave_e.engine import DiagnosticInputError, ENTER, EXIT, run_scenario


A, B, C = "600312.SH", "603228.SH", "603993.SH"


def fixture(closes, *, opens=None):
    """Explicit synthetic source fixture; never a historical/actual-day asset."""
    current = date(2030, 1, 1)
    result = []
    for index, close in enumerate(closes):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        opening = Decimal(str(opens[index] if opens is not None else close))
        closing = Decimal(str(close))
        stamp = current.strftime("%Y%m%d")
        result.append({"trade_date": stamp, "open": format(opening, "f"),
                       "high": format(max(opening, closing) + Decimal("0.001"), "f"),
                       "low": format(min(opening, closing) / 2, "f"), "close": format(closing, "f"),
                       "source_ref": {"fixture_only": True, "fixture_id": "WAVE_E_SYNTHETIC_PRICE",
                                      "date": stamp, "row_ordinal": str(index)}})
        current += timedelta(days=1)
    return result


def policy(**changes):
    # All values belong only to this explicitly synthetic test fixture. They
    # are neither production account settings nor fallback engine defaults.
    result = {"initial_cash_minor": "1000000", "commission_bps": "0", "min_commission_minor": "0",
              "sell_tax_bps": "0", "slippage_bps": "0", "lot_size": 1,
              "tradeability": "ASSUME_TRADEABLE_DIAGNOSTIC_ONLY"}
    result.update(changes)
    return result


def rising(count=90):
    return fixture([100 + index for index in range(count)])


def roundtrip():
    closes = list(range(100, 160)) + [80, 81, 82]
    opens = list(range(100, 160)) + [160, 81, 82]
    return fixture(closes, opens=opens)


class DiagnosticEngineTests(unittest.TestCase):
    def rejects(self, rows, p, code):
        with self.assertRaisesRegex(DiagnosticInputError, code):
            run_scenario(rows, p)

    def test_exact_public_shape_and_non_pit_labels(self):
        result = run_scenario({A: rising()}, policy())
        self.assertEqual(set(result), {"signals", "fills", "positions", "equity", "drawdown", "turnover", "audit", "assumptions"})
        self.assertEqual(result["audit"]["state"], "NON_PIT_DIAGNOSTIC")
        self.assertIn("NOT_HISTORICAL_PIT", result["audit"]["reason_codes"])
        self.assertFalse(result["audit"]["formal_backtest_eligible"])
        self.assertFalse(result["audit"]["production_eligible"])
        self.assertFalse(result["audit"]["historical_visibility_proven"])
        self.assertFalse(result["assumptions"]["native_object_issued"])

    def test_requires_all_explicit_policy_parameters(self):
        for key in policy():
            p = policy()
            del p[key]
            with self.subTest(missing=key):
                self.rejects({A: rising()}, p, "EXPLICIT_EXACT_SYNTHETIC_POLICY_REQUIRED")

    def test_policy_cannot_include_production_parameter_or_default(self):
        self.rejects({A: rising()}, policy(real_account="OWNER"), "EXPLICIT_EXACT_SYNTHETIC_POLICY_REQUIRED")

    def test_scope_unknown_empty_and_over_three_block(self):
        for rows in ({}, {"000001.SZ": rising()}, {A: rising(), B: rising(), C: rising(), "000001.SZ": rising()}):
            with self.subTest(scope=tuple(rows)):
                self.rejects(rows, policy(), "REQUIRED|SCOPE")

    def test_all_symbols_require_nonempty_data(self):
        for value in ([], None, {}):
            with self.subTest(kind=type(value).__name__):
                self.rejects({A: rising(), B: value}, policy(), "MISSING_DIAGNOSTIC_PRICE_ROWS")

    def test_missing_day_and_nonaligned_calendar_block_full_run(self):
        rows = rising()
        self.rejects({A: rows, B: rows[:20] + rows[21:]}, policy(), "NONALIGNED_OR_MISSING_SYMBOL_CALENDAR")

    def test_duplicate_session_blocked(self):
        rows = rising()
        rows[10] = deepcopy(rows[9])
        self.rejects({A: rows}, policy(), "DUPLICATE_PRICE_SESSION")

    def test_unsorted_session_blocked(self):
        rows = rising()
        rows[9], rows[10] = rows[10], rows[9]
        self.rejects({A: rows}, policy(), "PRICE_SESSIONS_NOT_SORTED")

    def test_calendar_and_date_format_not_coerced(self):
        for bad in ("20300230", "2030011", "2030-01-01", 20300101):
            rows = rising()
            rows[0]["trade_date"] = bad
            with self.subTest(kind=type(bad).__name__):
                self.rejects({A: rows}, policy(), "TRADE_DATE")

    def test_financial_industry_adjustment_fields_rejected(self):
        for key in ("net_profit", "industry", "adj_factor", "adjustment_version", "available_at"):
            rows = rising()
            rows[65][key] = "SYNTHETIC_NO_LEAK"
            with self.subTest(extra=key):
                self.rejects({A: rows}, policy(), "PRICE_ROW_EXACT_KEYS_REQUIRED_NO_FINANCE_ADJUSTMENT_INDUSTRY")

    def test_missing_price_field_rejected_not_imputed(self):
        rows = rising()
        del rows[3]["close"]
        self.rejects({A: rows}, policy(), "PRICE_ROW_EXACT_KEYS_REQUIRED")

    def test_floats_nonfinite_negative_zero_exponent_rejected(self):
        for bad in (1.2, "NaN", "Infinity", "-1", "0", "1e2", None, True):
            rows = rising()
            rows[0]["open"] = bad
            with self.subTest(kind=type(bad).__name__):
                self.rejects({A: rows}, policy(), "OPEN_POSITIVE_DECIMAL_STRING_REQUIRED")

    def test_ohlc_bounds_checked(self):
        rows = rising()
        rows[0]["high"] = "99"
        self.rejects({A: rows}, policy(), "OHLC_BOUNDS_INVALID")

    def test_empty_or_float_source_reference_rejected(self):
        for ref in ({}, {"hidden_float": [0.1]}, {"not_json": Decimal("1")}):
            rows = rising()
            rows[0]["source_ref"] = ref
            with self.subTest(keys=tuple(ref)):
                self.rejects({A: rows}, policy(), "SOURCE_REFERENCE")

    def test_invalid_money_and_policy_numeric_types_block(self):
        for key, bad in (("initial_cash_minor", "-1"), ("initial_cash_minor", "1.0"),
                         ("min_commission_minor", 5), ("commission_bps", "-0.1"),
                         ("sell_tax_bps", float("inf")), ("slippage_bps", "NaN"),
                         ("lot_size", 0), ("lot_size", True)):
            with self.subTest(parameter=key):
                self.rejects({A: rising()}, policy(**{key: bad}), "INVALID|REQUIRED")

    def test_nonpositive_slippage_adjusted_exit_price_blocks(self):
        self.rejects({A: rising()}, policy(slippage_bps="10000"), "SLIPPAGE_WOULD_MAKE_EXIT_PRICE_NONPOSITIVE")

    def test_oversized_decimal_is_rejected_not_ingestion_rounded(self):
        rows = rising()
        rows[0]["close"] = "1." + "1" * 101
        self.rejects({A: rows}, policy(), "DECIMAL_INPUT_EXCEEDS_PRECISION_100")

    def test_no_signal_without_complete_sixty_session_window(self):
        result = run_scenario({A: rising(59)}, policy())
        self.assertEqual(result["signals"], [])
        self.assertEqual(result["fills"], [])

    def test_ma20_ma60_and_twenty_return_independent_arithmetic(self):
        result = run_scenario({A: rising(61)}, policy())
        signal = result["signals"][0]
        self.assertEqual(signal["decision_index"], "59")
        self.assertEqual(Decimal(signal["ma20"]), Decimal("149.5"))
        self.assertEqual(Decimal(signal["ma60"]), Decimal("129.5"))
        self.assertEqual(Decimal(signal["source_close"]), Decimal("159"))
        self.assertEqual(signal["momentum_base_source_ref"]["source_ref"]["row_ordinal"], "39")
        self.assertEqual(len(signal["window_source_refs"]), 60)
        self.assertTrue(all(ref["trade_date"] <= signal["decision_date"] for ref in signal["window_source_refs"]))

    def test_strict_entry_equality_does_not_trigger(self):
        result = run_scenario({A: fixture([100] * 90)}, policy())
        self.assertEqual(result["signals"], [])

    def test_first_fill_is_next_open_not_signal_close(self):
        rows = roundtrip()
        result = run_scenario({A: rows}, policy())
        fill = result["fills"][0]
        self.assertEqual(fill["decision_date"], rows[59]["trade_date"])
        self.assertEqual(fill["fill_date"], rows[60]["trade_date"])
        self.assertEqual(fill["source_open"], "160")
        self.assertNotEqual(fill["fill_price"], result["signals"][0]["source_close"])

    def test_future_suffix_perturbation_and_prefix_invariance(self):
        original = rising(90)
        changed = deepcopy(original)
        for row in changed[70:]:
            row.update(open="9000", high="9001", low="8999", close="9000")
        first = run_scenario({A: original}, policy())
        second = run_scenario({A: changed}, policy())
        prefix = run_scenario({A: original[:65]}, policy())
        self.assertEqual(first["equity"][:65], second["equity"][:65])
        self.assertEqual(first["equity"][:65], prefix["equity"])
        self.assertEqual(first["fills"][:1], second["fills"][:1])
        self.assertEqual(first["signals"][:1], prefix["signals"])

    def test_same_fill_day_close_does_not_change_that_open_fill(self):
        rows = rising(62)
        other = deepcopy(rows)
        other[60].update(close="1", low="0.5")
        first = run_scenario({A: rows}, policy())
        second = run_scenario({A: other}, policy())
        self.assertEqual(first["fills"][0], second["fills"][0])
        self.assertEqual(first["signals"][0], second["signals"][0])
        self.assertEqual(second["signals"][1]["direction"], EXIT)

    def test_open_change_can_change_fill_but_not_prior_decision(self):
        rows = rising(61)
        changed = deepcopy(rows)
        changed[60].update(open="150", low="149")
        first = run_scenario({A: rows}, policy())
        second = run_scenario({A: changed}, policy())
        self.assertEqual(first["signals"], second["signals"])
        self.assertNotEqual(first["fills"][0]["gross_minor"], second["fills"][0]["gross_minor"])

    def test_terminal_pending_is_unfilled_without_invented_session(self):
        rows = rising(60)
        result = run_scenario({A: rows}, policy())
        self.assertEqual(len(result["signals"]), 1)
        self.assertEqual(result["signals"][0]["status"], "OBSERVED_CLOSE_DIAGNOSTIC_ONLY")
        self.assertEqual(result["audit"]["terminal_pending_signals"][0]["status"], "PENDING_NO_NEXT_OBSERVED_SESSION")
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["positions"][0]["quantity"], 0)

    def test_t_plus_one_even_when_fill_day_close_immediately_exits(self):
        rows = roundtrip()
        result = run_scenario({A: rows}, policy())
        entry, exit_fill = result["fills"]
        self.assertEqual(entry["direction"], ENTER)
        self.assertEqual(exit_fill["direction"], EXIT)
        self.assertEqual(entry["fill_date"], rows[60]["trade_date"])
        self.assertEqual(exit_fill["decision_date"], rows[60]["trade_date"])
        self.assertEqual(exit_fill["fill_date"], rows[61]["trade_date"])
        self.assertGreater(exit_fill["fill_date"], entry["fill_date"])
        self.assertEqual(result["audit"]["t_plus_one_violations"], [])

    def test_one_lot_no_duplicate_entry_no_terminal_liquidation(self):
        result = run_scenario({A: rising()}, policy(lot_size=7))
        self.assertEqual(len(result["signals"]), 1)
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["positions"][0]["quantity"], 7)
        self.assertFalse(result["drawdown"]["forced_terminal_liquidation"])
        self.assertIsNone(result["assumptions"]["maximum_holding_sessions"])

    def test_unknown_tradeability_blocks_every_hypothetical_fill(self):
        result = run_scenario({A: rising()}, policy(tradeability="BLOCK_UNKNOWN"))
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["positions"][0]["quantity"], 0)
        self.assertEqual(result["audit"]["initial_cash_minor"], result["audit"]["final_cash_minor"])
        self.assertTrue(all(outcome["status"] == "BLOCKED_TRADEABILITY_UNKNOWN" for outcome in result["audit"]["diagnostic_outcomes"]))
        self.assertFalse(result["assumptions"]["tradeability_proven"])

    def test_tradeability_assumption_is_labelled_not_proof(self):
        result = run_scenario({A: rising()}, policy())
        self.assertIn("ASSUMED_TRADEABLE_DIAGNOSTIC_ONLY", result["fills"][0]["reason_codes"])
        self.assertFalse(result["assumptions"]["tradeability_proven"])

    def test_fee_inclusive_affordability_exact_boundary(self):
        rows = rising(61)
        blocked = run_scenario({A: rows}, policy(initial_cash_minor="16000", min_commission_minor="1"))
        allowed = run_scenario({A: rows}, policy(initial_cash_minor="16001", min_commission_minor="1"))
        self.assertEqual(blocked["fills"], [])
        self.assertEqual(blocked["audit"]["diagnostic_outcomes"][0]["status"], "BLOCKED_FEE_INCLUSIVE_AFFORDABILITY")
        self.assertEqual(allowed["fills"][0]["cash_after_minor"], "0")

    def test_minimum_commission_below_at_above_boundary(self):
        for bps, expected in (("3", "50"), ("3.125", "50"), ("3.2", "51")):
            with self.subTest(bps=bps):
                result = run_scenario({A: rising(61)}, policy(lot_size=10, commission_bps=bps, min_commission_minor="50"))
                self.assertEqual(result["fills"][0]["commission_minor"], expected)

    def test_half_even_gross_and_commission_are_integer_minor(self):
        closes = [Decimal(index + 1) / 1000 for index in range(61)]
        for opening, expected_gross, expected_fee in (("0.025", "2", "0"), ("0.065", "6", "2")):
            opens = list(closes)
            opens[60] = Decimal(opening)
            with self.subTest(opening=opening):
                result = run_scenario({A: fixture(closes, opens=opens)}, policy(commission_bps="2500"))
                self.assertEqual(result["fills"][0]["gross_minor"], expected_gross)
                self.assertEqual(result["fills"][0]["commission_minor"], expected_fee)

    def test_exit_tax_half_even_and_entry_tax_zero(self):
        closes = [Decimal(index + 1) / 1000 for index in range(60)] + [Decimal("0.01"), Decimal("0.01")]
        opens = closes[:60] + [Decimal("0.060"), Decimal("0.065")]
        result = run_scenario({A: fixture(closes, opens=opens)}, policy(sell_tax_bps="2500"))
        self.assertEqual(result["fills"][0]["exit_tax_minor"], "0")
        self.assertEqual(result["fills"][1]["gross_minor"], "6")
        self.assertEqual(result["fills"][1]["exit_tax_minor"], "2")

    def test_directional_slippage_fee_tax_reconciles_independently(self):
        result = run_scenario({A: roundtrip()}, policy(initial_cash_minor="100000", slippage_bps="100", commission_bps="2", min_commission_minor="50", sell_tax_bps="10"))
        first, last = result["fills"]
        self.assertEqual(Decimal(first["fill_price"]), Decimal("161.60"))
        self.assertEqual(Decimal(last["fill_price"]), Decimal("80.19"))
        self.assertEqual((first["gross_minor"], last["gross_minor"]), ("16160", "8019"))
        self.assertEqual(last["exit_tax_minor"], "8")
        self.assertEqual(result["audit"]["final_cash_minor"], "91751")
        self.assertEqual(result["turnover"]["fees_paid_minor"], "108")

    def test_exits_before_entries_even_when_entry_symbol_sorts_first(self):
        a_closes = [100] * 60 + [160, 161]
        a_opens = a_closes[:61] + [10]
        b_closes = list(range(100, 160)) + [8, 9]
        b_opens = b_closes[:60] + [10, 10]
        c_closes = list(range(100, 162))
        c_opens = c_closes[:60] + [10, 10]
        result = run_scenario({C: fixture(c_closes, opens=c_opens), A: fixture(a_closes, opens=a_opens), B: fixture(b_closes, opens=b_opens)}, policy(initial_cash_minor="1000"))
        next_fills = [fill for fill in result["fills"] if fill["fill_index"] == "61"]
        self.assertEqual([(fill["symbol"], fill["direction"]) for fill in next_fills], [(B, EXIT), (A, ENTER)])
        self.assertEqual(result["audit"]["final_cash_minor"], "0")
        self.assertEqual(result["audit"]["cash_ordering"], "EXIT_THEN_ENTER_EXACT_SYMBOL_ORDER")

    def test_shared_cash_exact_symbol_order_not_mapping_insertion(self):
        one = run_scenario({C: rising(61), B: rising(61), A: rising(61)}, policy(initial_cash_minor="16000"))
        two = run_scenario({A: rising(61), B: rising(61), C: rising(61)}, policy(initial_cash_minor="16000"))
        self.assertEqual(one, two)
        self.assertEqual([fill["symbol"] for fill in one["fills"]], [A])
        self.assertEqual(sum(position["quantity"] for position in one["positions"]), 1)

    def test_zero_cash_has_no_margin_no_infinite_turnover(self):
        result = run_scenario({A: rising()}, policy(initial_cash_minor="0"))
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["drawdown"]["max_drawdown_ratio"], "0")
        self.assertIsNone(result["turnover"]["gross_to_initial_cash_ratio"])
        self.assertEqual(result["audit"]["final_cash_minor"], "0")

    def test_exit_costs_cannot_create_negative_cash(self):
        closes = list(range(100, 160)) + [80, 81]
        opens = list(range(100, 160)) + [160, 1]
        result = run_scenario({A: fixture(closes, opens=opens)}, policy(initial_cash_minor="16100", min_commission_minor="100", sell_tax_bps="10000"))
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["audit"]["diagnostic_outcomes"][1]["status"], "BLOCKED_FEE_INCLUSIVE_AFFORDABILITY")
        self.assertEqual(result["audit"]["final_cash_minor"], "0")

    def test_mark_close_drawdown_and_turnover_independent_reference(self):
        result = run_scenario({A: roundtrip()}, policy(initial_cash_minor="100000"))
        self.assertEqual(result["equity"][60]["cash_minor"], "84000")
        self.assertEqual(result["equity"][60]["marked_positions_minor"][A], "8000")
        self.assertEqual(result["equity"][60]["equity_minor"], "92000")
        self.assertEqual(Decimal(result["drawdown"]["max_drawdown_ratio"]), Decimal("0.08"))
        self.assertEqual(result["turnover"]["gross_turnover_minor"], "24100")
        self.assertEqual(Decimal(result["turnover"]["gross_to_initial_cash_ratio"]), Decimal("0.241"))
        self.assertEqual(result["audit"]["final_cash_minor"], "92100")

    def test_every_fill_and_final_ledger_conserves_integer_cash(self):
        result = run_scenario({A: roundtrip(), B: roundtrip(), C: roundtrip()}, policy(commission_bps="3.1", min_commission_minor="9", sell_tax_bps="5.7", slippage_bps="2.3"))
        previous = int(result["audit"]["initial_cash_minor"])
        for fill in result["fills"]:
            self.assertEqual(int(fill["cash_before_minor"]), previous)
            self.assertEqual(int(fill["cash_after_minor"]), previous + int(fill["cash_delta_minor"]))
            previous = int(fill["cash_after_minor"])
            self.assertGreaterEqual(previous, 0)
        self.assertEqual(str(previous), result["audit"]["final_cash_minor"])
        self.assertEqual(str(previous), result["audit"]["cash_reconciliation_minor"])
        for key in ("future_index_violations", "same_bar_fill_violations", "t_plus_one_violations", "ledger_mismatch_violations", "negative_cash_violations"):
            self.assertEqual(result["audit"][key], [])

    def test_source_decision_window_fill_and_marks_preserved(self):
        rows = rising(61)
        result = run_scenario({A: rows}, policy())
        self.assertEqual(result["signals"][0]["decision_source_ref"]["source_ref"], rows[59]["source_ref"])
        self.assertEqual(result["signals"][0]["window_source_refs"][0]["source_ref"], rows[0]["source_ref"])
        self.assertEqual(result["fills"][0]["fill_source_ref"]["source_ref"], rows[60]["source_ref"])
        self.assertEqual(result["equity"][60]["source_refs"][0]["source_ref"], rows[60]["source_ref"])

    def test_input_not_mutated_and_output_references_not_aliased(self):
        rows, p = {A: rising(61)}, policy()
        before_rows, before_policy = deepcopy(rows), deepcopy(p)
        result = run_scenario(rows, p)
        self.assertEqual(rows, before_rows)
        self.assertEqual(p, before_policy)
        original = json.dumps(result, sort_keys=True)
        rows[A][59]["source_ref"]["fixture_id"] = "CHANGED_AFTER_RUN"
        p["initial_cash_minor"] = "0"
        self.assertEqual(json.dumps(result, sort_keys=True), original)

    def test_outputs_have_no_floats_and_zero_fee_is_not_net_edge(self):
        result = run_scenario({A: rising()}, policy())

        def visit(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(result)
        self.assertEqual(result["turnover"]["fees_paid_minor"], "0")
        self.assertFalse(result["assumptions"]["fee_scenario_is_net_edge"])
        self.assertTrue(result["assumptions"]["all_policy_parameters_synthetic"])
        self.assertNotIn('"BUY"', json.dumps(result))
        self.assertNotIn('"SELL"', json.dumps(result))

    def test_deterministic_replay_byte_equal(self):
        rows = {A: roundtrip(), B: rising(len(roundtrip())), C: rising(len(roundtrip()))}
        p = policy(commission_bps="3.3", min_commission_minor="7", slippage_bps="2.1", sell_tax_bps="6.5")
        first = json.dumps(run_scenario(rows, p), sort_keys=True, separators=(",", ":"))
        second = json.dumps(run_scenario(rows, p), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_later_fill_does_not_rewrite_terminal_prefix_signal(self):
        rows = rising(61)
        prefix = run_scenario({A: rows[:60]}, policy())
        extended = run_scenario({A: rows}, policy())
        self.assertEqual(prefix["signals"], extended["signals"])
        self.assertEqual(prefix["audit"]["diagnostic_outcomes"], [])
        self.assertEqual(extended["audit"]["diagnostic_outcomes"][0]["status"], "FILLED_HYPOTHETICAL")
        self.assertEqual(prefix["audit"]["terminal_pending_signals"][0]["status"], "PENDING_NO_NEXT_OBSERVED_SESSION")
        self.assertEqual(extended["audit"]["terminal_pending_signals"], [])


if __name__ == "__main__":
    unittest.main()
