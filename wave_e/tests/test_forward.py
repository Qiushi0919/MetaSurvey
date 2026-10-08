"""Synthetic-only forward readiness positive controls and adversarial checks."""

import copy
import hashlib
import unittest

from wave_e.forward import (
    NAMESPACE, SCHEMA_VERSION, SYMBOLS, FixtureAuthority, FixtureLedger,
    ForwardBlocked, append_fixture_day, fixture_ledger_snapshot,
    issue_fixture_authority, new_fixture_ledger, readiness, run_real_forward,
)


def binding(label):
    return hashlib.sha256(("synthetic:" + label).encode()).hexdigest()


def fixtures(day="20261008", cutoff_ns="000000009"):
    iso = day[:4] + "-" + day[4:6] + "-" + day[6:]
    issuer = {
        "kind": "HUMAN_USER", "scope": "FIXTURE_ONLY",
        "subject": "SYNTHETIC_HUMAN_USER", "authorization_id": "fixture:owner-test",
        "issued_at": iso + "T16:00:02.000000001+08:00",
        "expires_at": iso + "T17:00:00.000000000+08:00",
    }
    pins = {name: binding(name + ":" + day) for name in
            ("source_hash", "rules_hash", "code_hash", "schema_hash", "receipt_hash")}
    evidence = {
        "kind": "SYNTHETIC_SOURCE_OBSERVATION", "namespace": NAMESPACE,
        "schema_version": SCHEMA_VERSION, "observed_universe": list(SYMBOLS),
        "source_day": day,
        "calendar_session": {"kind": "SYNTHETIC_OPEN_SESSION", "venue": "SSE",
                             "source_ref": "fixture://calendar/" + day,
                             "session_day": day,
                             "market_close": iso + "T15:00:00.000000000+08:00"},
        "published_at": iso + "T15:00:00.000000001+08:00",
        "available_at": iso + "T16:00:00.000000001+08:00",
        "retrieved_at": iso + "T16:00:02.000000000+08:00",
        "decision_cutoff": iso + "T16:00:02." + cutoff_ns + "+08:00",
        "bindings": pins,
    }
    return issuer, evidence


def record_for(ledger, evidence):
    return {
        "decision_cutoff": evidence["decision_cutoff"],
        "observed_universe": list(SYMBOLS), "candidate_or_no_candidate": "NO_CANDIDATE",
        "signal_source": {"kind": "SYNTHETIC_RULE_ENGINE",
                          "source_day": evidence["source_day"],
                          "source_hash": evidence["bindings"]["source_hash"],
                          "receipt_hash": evidence["bindings"]["receipt_hash"]},
        "hypothetical_entry": [], "hypothetical_exit": [], "tradeability": "UNKNOWN",
        "cost_assumptions": {"kind": "SYNTHETIC_DPU",
                             "fixture_policy_ref": "fixture://cost/explicit-test-policy",
                             "actual_account_config": "UNSET_REQUIRED"},
        "risk_state": "UNKNOWN_UNSET_REQUIRED",
        "unknowns": ["actual_account_cost_risk", "provider_license", "historical_pit",
                     "tradeability"],
        "reason_codes": ["FIXTURE_ONLY", "NOT_ACTUAL_FORWARD_DAY", "UNSET_REQUIRED",
                         "TRADEABILITY_UNKNOWN", "NO_CANDIDATE"],
        "predecessor_hash": fixture_ledger_snapshot(ledger)["head_hash"],
        "source_day": evidence["source_day"], "namespace": NAMESPACE,
        "schema_version": SCHEMA_VERSION, "bindings": copy.deepcopy(evidence["bindings"]),
    }


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.issuer, self.evidence = fixtures()
        self.ledger = new_fixture_ledger()

    def authority(self):
        return issue_fixture_authority(self.issuer, self.evidence)

    def assertBlocked(self, code, operation):
        with self.assertRaisesRegex(ForwardBlocked, "^" + code + "$"):
            operation()

    def bad_evidence(self, code, alter):
        alter(self.evidence)
        self.assertBlocked(code, self.authority)

    def bad_record(self, code, alter):
        ledger = new_fixture_ledger()
        authority = self.authority()
        record = record_for(ledger, self.evidence)
        alter(record)
        self.assertBlocked(code, lambda: append_fixture_day(ledger, authority, record))
        # A failed append must not consume the authority or change the ledger.
        good = append_fixture_day(ledger, authority, record_for(ledger, self.evidence))
        self.assertEqual(1, fixture_ledger_snapshot(good)["fixture_day_count"])
        self.assertEqual(0, fixture_ledger_snapshot(good)["actual_forward_days"])

    def test_readiness_prepared_but_all_actual_start_blocked(self):
        state = readiness()
        self.assertTrue(state["engine_ready"])
        self.assertEqual("BLOCKED", state["real_start_state"])
        self.assertEqual("UNAVAILABLE_THIS_WAVE", state["real_authority_issuance"])
        self.assertEqual(0, state["actual_forward_days"])
        self.assertEqual(30, state["unset_actual_parameter_count"])
        self.assertEqual("UNSET_REQUIRED", state["actual_settings"])
        self.assertEqual("PENDING", state["snapshot_b_state"])
        self.assertFalse(state["native_promotion"])
        self.assertFalse(state["scheduling_enabled"])

    def test_real_runner_always_blocks_self_asserted_receipts_and_llm_approve(self):
        for arguments in ({}, {"approved": True}, {"receipt_verified": True},
                          {"issuer": "LLM", "decision": "APPROVE"},
                          {"owner_authorized": True, "actual_forward_days": 20}):
            with self.subTest(arguments=list(arguments)):
                self.assertBlocked("REAL_FORWARD_NOT_AUTHORIZED",
                                   lambda: run_real_forward(**arguments))

    def test_positive_human_fixture_appends_but_never_counts_actual_day(self):
        authority = self.authority()
        record = record_for(self.ledger, self.evidence)
        result = append_fixture_day(self.ledger, authority, record)
        snapshot = fixture_ledger_snapshot(result)
        self.assertEqual("FIXTURE_ONLY", snapshot["scope"])
        self.assertEqual("DISPLAY_ONLY", snapshot["snapshot_authority"])
        self.assertEqual(0, snapshot["actual_forward_days"])
        self.assertEqual(1, snapshot["fixture_day_count"])
        self.assertFalse(snapshot["native_promotion"])
        self.assertEqual(record["predecessor_hash"], snapshot["records"][0]["predecessor_hash"])
        self.assertEqual(snapshot["head_hash"], snapshot["records"][0]["daily_hash"])
        self.assertNotEqual(record["predecessor_hash"], snapshot["head_hash"])
        self.assertBlocked("REAL_FORWARD_NOT_AUTHORIZED", lambda: run_real_forward(result))

    def test_two_day_append_preserves_first_record_and_hash(self):
        first = append_fixture_day(self.ledger, self.authority(), record_for(self.ledger, self.evidence))
        before = fixture_ledger_snapshot(first)
        issuer2, evidence2 = fixtures("20261009")
        second = append_fixture_day(first, issue_fixture_authority(issuer2, evidence2),
                                    record_for(first, evidence2))
        after = fixture_ledger_snapshot(second)
        self.assertEqual(before["records"][0], after["records"][0])
        self.assertEqual(before["head_hash"], after["records"][1]["predecessor_hash"])
        self.assertEqual(2, after["fixture_day_count"])
        self.assertEqual(0, after["actual_forward_days"])

    def test_empty_fixture_and_detached_readiness_mutation_cannot_start_real(self):
        snapshot = fixture_ledger_snapshot(self.ledger)
        snapshot["actual_forward_days"] = 20
        snapshot["scope"] = "REAL"
        changed = readiness()
        changed["real_start_state"] = "APPROVED"
        self.assertEqual(0, fixture_ledger_snapshot(self.ledger)["actual_forward_days"])
        self.assertEqual("BLOCKED", readiness()["real_start_state"])
        self.assertBlocked("REAL_FORWARD_NOT_AUTHORIZED", lambda: run_real_forward(snapshot, changed))

    def test_no_human_authority_is_rejected(self):
        self.issuer = {}
        self.assertBlocked("HUMAN_FIXTURE_AUTHORITY_SCHEMA_INVALID", self.authority)

    def test_llm_approve_does_not_issue_fixture_authority(self):
        self.issuer["kind"] = "LLM"
        self.assertBlocked("HUMAN_FIXTURE_AUTHORITY_REQUIRED", self.authority)

    def test_real_human_scope_cannot_be_issued_from_caller_dictionary(self):
        self.issuer["scope"] = "REAL_FORWARD"
        self.issuer["subject"] = "OWNER"
        self.assertBlocked("HUMAN_FIXTURE_AUTHORITY_REQUIRED", self.authority)

    def test_boolean_authority_is_not_a_handle(self):
        self.assertBlocked("REGISTERED_FIXTURE_AUTHORITY_REQUIRED",
                           lambda: append_fixture_day(self.ledger, True,
                                                      record_for(self.ledger, self.evidence)))

    def test_dictionary_receipt_is_not_a_handle(self):
        self.assertBlocked("REGISTERED_FIXTURE_AUTHORITY_REQUIRED",
                           lambda: append_fixture_day(self.ledger, {"verified": True},
                                                      record_for(self.ledger, self.evidence)))

    def test_authority_shallow_copy_is_not_registered(self):
        authority = copy.copy(self.authority())
        self.assertBlocked("FIXTURE_AUTHORITY_IDENTITY_OR_SEAL_INVALID",
                           lambda: append_fixture_day(self.ledger, authority,
                                                      record_for(self.ledger, self.evidence)))

    def test_authority_reseal_or_direct_constructor_is_not_registered(self):
        issued = self.authority()
        authority = FixtureAuthority(issued.authority_id, copy.deepcopy(issued._body))
        self.assertBlocked("FIXTURE_AUTHORITY_IDENTITY_OR_SEAL_INVALID",
                           lambda: append_fixture_day(self.ledger, authority,
                                                      record_for(self.ledger, self.evidence)))

    def test_authority_payload_tamper_fails_seal_check(self):
        authority = self.authority()
        authority._body["evidence"]["bindings"]["source_hash"] = binding("tamper")
        self.assertBlocked("FIXTURE_AUTHORITY_IDENTITY_OR_SEAL_INVALID",
                           lambda: append_fixture_day(self.ledger, authority,
                                                      record_for(self.ledger, self.evidence)))

    def test_issuer_or_evidence_original_mutation_cannot_change_issued_authority(self):
        authority = self.authority()
        original = record_for(self.ledger, self.evidence)
        self.issuer["kind"] = "LLM"
        self.evidence["bindings"]["source_hash"] = binding("changed-original")
        result = append_fixture_day(self.ledger, authority, original)
        self.assertEqual(0, fixture_ledger_snapshot(result)["actual_forward_days"])

    def test_october_six_and_seven_cannot_be_sessions(self):
        for day in ("20261006", "20261007"):
            with self.subTest(day=day):
                issuer, evidence = fixtures(day)
                self.assertBlocked("FIXTURE_SESSION_CLOSED",
                                   lambda: issue_fixture_authority(issuer, evidence))

    def test_weekend_calendar_claim_cannot_be_a_session(self):
        issuer, evidence = fixtures("20261010")
        self.assertBlocked("FIXTURE_SESSION_CLOSED",
                           lambda: issue_fixture_authority(issuer, evidence))

    def test_september_thirty_retrieval_replay_not_new_day(self):
        issuer, evidence = fixtures("20260930")
        self.assertBlocked("SOURCE_DAY_NOT_NEW",
                           lambda: issue_fixture_authority(issuer, evidence))

    def test_source_day_calendar_day_mismatch_blocks(self):
        self.bad_evidence("SESSION_PROOF_BINDING_INVALID",
                          lambda e: e["calendar_session"].update(session_day="20261009"))

    def test_boolean_calendar_assertion_not_proof(self):
        self.bad_evidence("SESSION_PROOF_SCHEMA_INVALID",
                          lambda e: e.update(calendar_session={"is_open": True}))

    def test_live_receipt_kind_cannot_be_treated_as_fixture_source(self):
        self.bad_evidence("SYNTHETIC_EVIDENCE_REQUIRED",
                          lambda e: e.update(kind="REAL_SOURCE_OBSERVATION"))

    def test_null_or_date_only_clock_is_not_imputed(self):
        for value in (None, "20261008", "2026-10-08"):
            with self.subTest(value=value):
                issuer, evidence = fixtures()
                evidence["available_at"] = value
                self.assertBlocked("CLOCK_PRECISION_OR_TIMEZONE_INVALID",
                                   lambda: issue_fixture_authority(issuer, evidence))

    def test_midnight_timestamp_cannot_impute_source_availability(self):
        self.bad_evidence("MIDNIGHT_IMPUTATION_FORBIDDEN",
                          lambda e: e.update(available_at="2026-10-08T00:00:00.000000000+08:00"))

    def test_naive_utc_and_millisecond_timestamps_block(self):
        for value in ("2026-10-08T16:00:00.000000001", "2026-10-08T08:00:00.000000001Z",
                      "2026-10-08T16:00:00.001+08:00"):
            with self.subTest(kind=value[-6:]):
                issuer, evidence = fixtures()
                evidence["available_at"] = value
                self.assertBlocked("CLOCK_PRECISION_OR_TIMEZONE_INVALID",
                                   lambda: issue_fixture_authority(issuer, evidence))

    def test_source_clock_future_by_one_nanosecond_blocks(self):
        self.bad_evidence("SOURCE_CLOCK_ORDER_INVALID",
                          lambda e: e.update(retrieved_at="2026-10-08T16:00:02.000000010+08:00"))

    def test_authority_future_by_one_nanosecond_blocks(self):
        self.issuer["issued_at"] = "2026-10-08T16:00:02.000000010+08:00"
        self.assertBlocked("AUTHORITY_CLOCK_ORDER_INVALID", self.authority)

    def test_cutoff_on_authority_expiry_is_expired(self):
        self.issuer["expires_at"] = self.evidence["decision_cutoff"]
        self.assertBlocked("AUTHORITY_CLOCK_ORDER_INVALID", self.authority)

    def test_published_before_market_close_blocks(self):
        self.bad_evidence("SOURCE_CLOCK_ORDER_INVALID",
                          lambda e: e.update(published_at="2026-10-08T14:59:59.999999999+08:00"))

    def test_available_before_publication_blocks(self):
        self.bad_evidence("SOURCE_CLOCK_ORDER_INVALID",
                          lambda e: e.update(available_at="2026-10-08T15:00:00.000000000+08:00"))

    def test_retrieval_on_different_day_cannot_make_old_source_fresh(self):
        self.bad_evidence("SOURCE_CLOCK_DAY_MISMATCH",
                          lambda e: e.update(retrieved_at="2026-10-09T16:00:02.000000000+08:00"))

    def test_market_close_must_be_explicit_fifteen_hundred_same_session(self):
        self.bad_evidence("SESSION_CLOSE_INVALID", lambda e: e["calendar_session"].update(
            market_close="2026-10-08T14:00:00.000000000+08:00"))

    def test_universe_missing_extra_or_reordered_blocks(self):
        for symbols in (list(SYMBOLS[:-1]), list(SYMBOLS) + ["000001.SZ"], list(reversed(SYMBOLS))):
            with self.subTest(size=len(symbols)):
                issuer, evidence = fixtures()
                evidence["observed_universe"] = symbols
                self.assertBlocked("UNIVERSE_OR_ORDER_DRIFT",
                                   lambda: issue_fixture_authority(issuer, evidence))

    def test_namespace_and_schema_version_drift_block(self):
        for field, value, code in (("namespace", "CORE_40", "NAMESPACE_DRIFT"),
                                   ("schema_version", "2.0.0", "SCHEMA_VERSION_DRIFT")):
            with self.subTest(field=field):
                issuer, evidence = fixtures()
                evidence[field] = value
                self.assertBlocked(code, lambda: issue_fixture_authority(issuer, evidence))

    def test_all_five_bindings_are_required_valid_hashes(self):
        self.bad_evidence("BINDINGS_SCHEMA_INVALID",
                          lambda e: e["bindings"].pop("receipt_hash"))

    def test_non_hash_binding_rejected(self):
        self.bad_evidence("BINDING_HASH_INVALID", lambda e: e["bindings"].update(code_hash="APPROVE"))

    def test_each_hash_binding_drift_between_authority_and_record_blocks(self):
        for field in self.evidence["bindings"]:
            with self.subTest(field=field):
                ledger = new_fixture_ledger()
                authority = self.authority()
                record = record_for(ledger, self.evidence)
                record["bindings"][field] = binding("different-" + field)
                self.assertBlocked("FIXTURE_AUTHORITY_RECORD_BINDING_DRIFT",
                                   lambda: append_fixture_day(ledger, authority, record))

    def test_signal_source_hash_or_receipt_drift_blocks(self):
        for field in ("source_hash", "receipt_hash"):
            with self.subTest(field=field):
                self.bad_record("SIGNAL_SOURCE_BINDING_DRIFT",
                                lambda r: r["signal_source"].update({field: binding("drift")}))

    def test_llm_signal_source_not_accepted(self):
        self.bad_record("SIGNAL_SOURCE_BINDING_DRIFT", lambda r: r["signal_source"].update(kind="LLM"))

    def test_predecessor_conflict_does_not_consume_authority(self):
        self.bad_record("FIXTURE_PREDECESSOR_CONFLICT",
                        lambda r: r.update(predecessor_hash=binding("wrong-predecessor")))

    def test_duplicate_day_with_new_human_fixture_authority_blocks(self):
        first = append_fixture_day(self.ledger, self.authority(), record_for(self.ledger, self.evidence))
        authority2 = self.authority()
        self.assertBlocked("DUPLICATE_FIXTURE_DAY",
                           lambda: append_fixture_day(first, authority2, record_for(first, self.evidence)))
        self.assertEqual(0, fixture_ledger_snapshot(first)["actual_forward_days"])

    def test_receipt_replay_on_new_chain_cannot_reuse_consumed_authority(self):
        authority = self.authority()
        append_fixture_day(self.ledger, authority, record_for(self.ledger, self.evidence))
        other = new_fixture_ledger()
        self.assertBlocked("FIXTURE_AUTHORITY_ALREADY_USED",
                           lambda: append_fixture_day(other, authority, record_for(other, self.evidence)))

    def test_old_ledger_head_cannot_overwrite_or_fork_successor(self):
        first = append_fixture_day(self.ledger, self.authority(), record_for(self.ledger, self.evidence))
        issuer2, evidence2 = fixtures("20261009")
        authority2 = issue_fixture_authority(issuer2, evidence2)
        old_record = {**record_for(first, evidence2), "predecessor_hash": self.ledger._body["head_hash"]}
        self.assertBlocked("STALE_FIXTURE_LEDGER_HANDLE",
                           lambda: append_fixture_day(self.ledger, authority2, old_record))

    def test_backdated_day_cannot_be_inserted(self):
        issuer2, evidence2 = fixtures("20261009")
        first = append_fixture_day(self.ledger, issue_fixture_authority(issuer2, evidence2),
                                   record_for(self.ledger, evidence2))
        self.assertBlocked("FIXTURE_DAY_ORDER_INVALID",
                           lambda: append_fixture_day(first, self.authority(),
                                                      record_for(first, self.evidence)))

    def test_copied_ledger_or_reconstructed_ledger_is_not_registered(self):
        for ledger in (copy.copy(self.ledger), FixtureLedger(self.ledger.ledger_id,
                                                            copy.deepcopy(self.ledger._body))):
            with self.subTest(kind=type(ledger).__name__):
                self.assertBlocked("FIXTURE_LEDGER_IDENTITY_OR_SEAL_INVALID",
                                   lambda: fixture_ledger_snapshot(ledger))

    def test_internal_ledger_count_tampering_fails_seal(self):
        self.ledger._body["actual_forward_days"] = 20
        self.assertBlocked("FIXTURE_LEDGER_IDENTITY_OR_SEAL_INVALID",
                           lambda: fixture_ledger_snapshot(self.ledger))

    def test_snapshot_dictionary_cannot_replace_registered_ledger(self):
        snapshot = fixture_ledger_snapshot(self.ledger)
        self.assertBlocked("REGISTERED_FIXTURE_LEDGER_REQUIRED",
                           lambda: append_fixture_day(snapshot, self.authority(),
                                                      record_for(self.ledger, self.evidence)))

    def test_caller_daily_hash_or_actual_count_flag_not_allowed(self):
        for key, value in (("daily_hash", binding("reseal")), ("actual_forward_days", 1),
                           ("native_promotion", True)):
            with self.subTest(key=key):
                self.bad_record("FIXTURE_RECORD_SCHEMA_INVALID", lambda r: r.update({key: value}))

    def test_unknown_erasure_blocked(self):
        self.bad_record("UNKNOWN_ERASURE_FORBIDDEN", lambda r: r.update(unknowns=[]))

    def test_actual_account_cost_and_risk_promotions_blocked(self):
        self.bad_record("COST_ACTUAL_PARAMETER_PROMOTION_FORBIDDEN",
                        lambda r: r["cost_assumptions"].update(actual_account_config="15000"))
        self.bad_record("RISK_ACTUAL_PARAMETER_PROMOTION_FORBIDDEN", lambda r: r.update(risk_state="APPROVED"))

    def test_synthetic_candidate_with_explicit_tradeability_assumption_is_fixture_only(self):
        record = record_for(self.ledger, self.evidence)
        record["candidate_or_no_candidate"] = "CANDIDATE"
        record["tradeability"] = "ASSUME_TRADEABLE_FIXTURE_ONLY"
        record["reason_codes"].remove("TRADEABILITY_UNKNOWN")
        record["reason_codes"].append("SYNTHETIC_TRADEABILITY_ASSUMPTION")
        record["hypothetical_entry"] = [{"symbol": SYMBOLS[0], "direction": "ENTER_HYPOTHETICAL",
                                         "quantity": 100, "price_dpu": "10.125000"}]
        result = append_fixture_day(self.ledger, self.authority(), record)
        self.assertEqual(0, fixture_ledger_snapshot(result)["actual_forward_days"])
        self.assertEqual("SYNTHETIC_DPU", fixture_ledger_snapshot(result)["records"][0]["cost_assumptions"]["kind"])

    def test_unknown_tradeability_blocks_even_hypothetical_entry(self):
        self.bad_record("TRADEABILITY_UNKNOWN_BLOCKS_HYPOTHETICAL", lambda r: r.update(
            candidate_or_no_candidate="CANDIDATE",
            hypothetical_entry=[{"symbol": SYMBOLS[0], "direction": "ENTER_HYPOTHETICAL",
                                 "quantity": 100, "price_dpu": "1"}]))

    def test_no_candidate_cannot_contain_entry(self):
        self.bad_record("NO_CANDIDATE_ENTRY_FORBIDDEN", lambda r: r.update(
            hypothetical_entry=[{"symbol": SYMBOLS[0], "direction": "ENTER_HYPOTHETICAL",
                                 "quantity": 100, "price_dpu": "1"}]))

    def test_boolean_or_container_enum_does_not_bypass_state_validation(self):
        for value in (True, {}, []):
            with self.subTest(value_type=type(value).__name__):
                self.bad_record("CANDIDATE_STATE_INVALID", lambda r: r.update(candidate_or_no_candidate=value))
                self.bad_record("TRADEABILITY_STATE_INVALID", lambda r: r.update(tradeability=value))

    def test_same_day_hypothetical_entry_exit_blocked(self):
        entry = {"symbol": SYMBOLS[0], "direction": "ENTER_HYPOTHETICAL", "quantity": 100, "price_dpu": "1"}
        exit_ = {**entry, "direction": "EXIT_HYPOTHETICAL"}
        self.bad_record("SAME_DAY_HYPOTHETICAL_ROUNDTRIP_FORBIDDEN", lambda r: r.update(
            candidate_or_no_candidate="CANDIDATE", hypothetical_entry=[entry], hypothetical_exit=[exit_]))

    def test_native_order_direction_is_not_accepted(self):
        self.bad_record("HYPOTHETICAL_DIRECTION_INVALID", lambda r: r.update(
            candidate_or_no_candidate="CANDIDATE",
            hypothetical_entry=[{"symbol": SYMBOLS[0], "direction": "BUY", "quantity": 100, "price_dpu": "1"}]))

    def test_nonfinite_or_float_synthetic_price_not_accepted(self):
        for value in ("NaN", "Infinity", "0", "-1", 1.25):
            with self.subTest(value_type=type(value).__name__):
                self.bad_record("HYPOTHETICAL_PRICE_INVALID", lambda r: r.update(
                    candidate_or_no_candidate="CANDIDATE",
                    hypothetical_entry=[{"symbol": SYMBOLS[0], "direction": "ENTER_HYPOTHETICAL",
                                         "quantity": 100, "price_dpu": value}]))

    def test_source_record_input_or_snapshot_mutation_does_not_change_stored_day(self):
        record = record_for(self.ledger, self.evidence)
        result = append_fixture_day(self.ledger, self.authority(), record)
        before = fixture_ledger_snapshot(result)
        record["unknowns"].clear()
        detached = fixture_ledger_snapshot(result)
        detached["records"][0]["bindings"]["code_hash"] = binding("caller-change")
        detached["records"][0]["unknowns"].clear()
        self.assertEqual(before, fixture_ledger_snapshot(result))


if __name__ == "__main__":
    unittest.main()
