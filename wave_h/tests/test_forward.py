"""Native-shaped synthetic sources: never actual grants or market sessions."""
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from wave_h import forward as f
from wave_h import collector
from wave_h.common import ARCHIVE, ROOT, SYMBOLS, bindings, canonical, digest, ref, seal


def put(path, obj, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(obj if raw else canonical(obj)); path.chmod(0o600)
    return ref(path)


def native(api, symbol, day, seed=0):
    ymd = day.replace("-", "")
    if api == "trade_cal": row = ["SSE", ymd, 1, "20260930"]
    elif api == "daily": row = [symbol, ymd, str(10 + seed), str(12 + seed), str(9 + seed), str(11 + seed), "10", "1", "10", "100", "110"]
    elif api == "stock_basic": row = [symbol, symbol[:6], "SYNTHETIC_SECURITY", "SSE", "CNY", "L", "20000101", None]
    elif api == "suspend_d": row = None
    else: row = [symbol, ymd, "10", "11", "9"]
    return canonical({"code": 0, "msg": None, "data": {"fields": f._FIELDS[api], "items": [] if row is None else [row]}})


def fixture(directory, day="2026-10-08", suffix="one", anchor_ref=None, optional_denied=False):
    """All prices/status/session facts here are explicitly synthetic."""
    directory.mkdir(mode=0o700)
    if anchor_ref is None:
        a_refs = [put(directory / ("A-" + s + ".json"), native("daily", s, "2026-09-30"), True) for s in SYMBOLS]
        a = {"version": "1.0.0", "kind": "OFFLINE_SIMULATION_REFERENCE_A", "capture_id": "sim:A",
             "session_date": "2026-09-30", "retrieved_at": "2026-10-05T07:01:00Z", "observed_universe": list(SYMBOLS),
             "source_original_refs": a_refs, "raw_observation_hash": digest(a_refs), "source_policy_hash": bindings()["policy_hash"],
             "rules_hash": bindings()["strategy_hash"], "source_admission": "BLOCKED", "historical_visibility_proven": False}
        anchor_ref = put(directory / "A.json", a)
    evidence = put(directory / "simulation-session-original.json", {"kind": "SYNTHETIC_NOT_ACTUAL_MARKET_EVIDENCE", "day": day})
    witness = {"version": "1.0.0", "kind": "OFFLINE_SIMULATION_SESSION_WITNESS", "session": day, "symbols": list(SYMBOLS),
               "actual_session_open": True, "eod_observed": True, "observed_at": day + "T07:00:01.000Z", "precision": "MILLISECOND",
               "original_refs": [evidence], "witness_source": "SYNTHETIC_NO_ACTUAL_AUTHORITY"}
    witness_ref = put(directory / "witness.json", witness)
    plan = collector.build_plan(day, witness_ref, anchor_ref)
    started, retrieved = day + "T07:01:00.123Z", day + "T07:02:00.123456Z"
    entries = []
    for job in plan["jobs"]:
        api, symbol = job["api_name"], job["symbol"]
        raw = native(api, symbol, day, int(day[-2:]))
        if optional_denied and not job["mandatory"]: raw = canonical({"code": -1, "msg": "permission denied", "data": None})
        raw_ref = put(directory / (job["job_id"] + ".raw.json"), raw, True)
        request_id = digest({"endpoint": plan["endpoint"], "source_identity": plan["source_identity"], "source_schema_version": plan["source_schema_version"], "session": day, "plan_hash": plan["plan_hash"], "job": job})
        clock = {"version": "1.0.0", "kind": "OFFLINE_SIMULATION_CAPTURE_CLOCK", "mode": "OFFLINE_SIMULATION",
                 "capture_id": "sim:" + suffix, "job_id": job["job_id"], "request_identity": request_id, "source_identity": plan["source_identity"],
                 "source_schema_version": plan["source_schema_version"], "session": day, "started_at": started, "retrieved_at": retrieved,
                 "retrieved_precision": "MICROSECOND", "event_time": day, "event_precision": "DATE_ONLY", "published_at": None, "published_precision": "UNKNOWN",
                 "source_available_at": None, "source_available_precision": "UNKNOWN", "current_available_at": retrieved,
                 "current_available_precision": "MICROSECOND", "visibility_basis": "CURRENT_CAPTURE_COMPLETED_NOT_HISTORICAL_FIRST_VISIBLE",
                 "historical_visibility_proven": False, "source_response_hash": raw_ref["sha256"]}
        clock_ref = put(directory / (job["job_id"] + ".clock.json"), clock)
        status = "API_DENIED" if optional_denied and not job["mandatory"] else "EMPTY" if api == "suspend_d" else "SUCCESS"
        entries.append({"job": job, "request_identity": request_id, "status": status,
                        "reason_code": "ENTITLEMENT_NOT_GRANTED" if status == "API_DENIED" else "SOURCE_EMPTY_NOT_COMPLETE_STATUS_PROOF" if status == "EMPTY" else None,
                        "raw_ref": raw_ref, "clock_ref": clock_ref, "source_response_hash": raw_ref["sha256"],
                        "row_count": None if status == "API_DENIED" else 0 if status == "EMPTY" else 1})
    unknowns = [{"symbol": s, "field": field, "state": "UNKNOWN", "reason_code": "CURRENT_RESPONSE_NOT_COMPLETE_VERIFIED_STATE"}
                for s in SYMBOLS for field in ("ST_NAME_HISTORY", "SUSPENSION_COMPLETE_STATE", "CORPORATE_ACTION_COMPLETENESS", "PRICE_LIMIT_REGIME", "PROVIDER_LICENSE_TRANSPORT")]
    manifest = seal({"version": "1.0.0", "kind": "OFFLINE_SIMULATION_CAPTURE", "mode": "OFFLINE_SIMULATION", "capture_id": "sim:" + suffix,
                     "plan": plan, "plan_hash": plan["plan_hash"], "policy_hash": plan["bindings"]["policy_hash"], "strategy_hash": plan["bindings"]["strategy_hash"],
                     "source_schema_version": plan["source_schema_version"], "source_identity": plan["source_identity"], "endpoint": plan["endpoint"], "session": day,
                     "symbols": list(SYMBOLS), "started_at": started, "completed_at": retrieved, "clock_precision": "MICROSECOND", "jobs": entries,
                     "source_session_evidence_ref": witness_ref, "snapshot_a_ref": anchor_ref, "capture_authorization": None,
                     "coverage": {"requested_symbols": list(SYMBOLS), "observed_daily_symbols": list(SYMBOLS), "mandatory_daily_count": 3,
                                  "session_calendar_consistent": True, "planned_calendar_is_actual_session_proof": False},
                     "status_unknowns": unknowns, "source_admission": "BLOCKED", "historical_visibility_proven": False,
                     "safe_to_trade": False, "decision": "NO_DECISION", "actual_forward_days": 0})
    return plan, put(directory / "capture-manifest.json", manifest)


class ForwardTests(unittest.TestCase):
    def setUp(self):
        base = ARCHIVE / "forward"; base.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory = Path(tempfile.mkdtemp(prefix="tests-", dir=base)); self.directory.chmod(0o700)
        self.plan, self.manifest_ref = fixture(self.directory / "capture-one")
        self.snapshot = f.issue_simulation_snapshot(self.manifest_ref, self.plan)
        self.path = self.directory / "forward.wave-h.simulation.sqlite3"
        self.genesis = f.create_simulation_store(self.path)

    def tearDown(self): shutil.rmtree(self.directory)

    def edit_manifest(self, mutate):
        value = json.loads(Path(self.manifest_ref["path"]).read_bytes()); mutate(value)
        value.pop("content_hash"); self.manifest_ref = put(Path(self.manifest_ref["path"]), seal(value))

    def edit_job_original(self, index, mutate):
        value = json.loads(Path(self.manifest_ref["path"]).read_bytes()); entry = value["jobs"][index]
        source = json.loads(Path(entry["raw_ref"]["path"]).read_bytes()); mutate(source)
        entry["raw_ref"] = put(Path(entry["raw_ref"]["path"]), source); entry["source_response_hash"] = entry["raw_ref"]["sha256"]
        clock = json.loads(Path(entry["clock_ref"]["path"]).read_bytes()); clock["source_response_hash"] = entry["source_response_hash"]
        entry["clock_ref"] = put(Path(entry["clock_ref"]["path"]), clock)
        value.pop("content_hash"); self.manifest_ref = put(Path(self.manifest_ref["path"]), seal(value))

    def edit_clock(self, mutate):
        value = json.loads(Path(self.manifest_ref["path"]).read_bytes()); entry = value["jobs"][1]
        clock = json.loads(Path(entry["clock_ref"]["path"]).read_bytes()); mutate(clock)
        entry["clock_ref"] = put(Path(entry["clock_ref"]["path"]), clock)
        value.pop("content_hash"); self.manifest_ref = put(Path(self.manifest_ref["path"]), seal(value))

    def test_review_reopens_all_raw_without_producer_parser(self):
        with patch.object(collector, "parse_native", side_effect=AssertionError("producer parser used")), patch.object(collector, "reopen_capture", side_effect=AssertionError("producer summary used")):
            result = f.review_capture(self.manifest_ref, self.plan)
        self.assertFalse(result["is_authority"]); self.assertTrue(result["independently_reopened"])
        self.assertEqual(result["coverage"]["mandatory_daily_count"], 3)
        self.assertEqual(len(result["original_refs"]), 33); self.assertEqual(result["actual_forward_days"], 0)
        self.assertTrue(all(x["state"] == "UNKNOWN" for x in result["status_unknowns"]))

    def test_optional_denial_identical_raw_keeps_unknown(self):
        p, r = fixture(self.directory / "denied", suffix="denied", optional_denied=True)
        self.assertEqual(len(f.review_capture(r, p)["status_unknowns"]), 15)

    def test_missing_symbol_fails_even_resealed_summary(self):
        self.edit_manifest(lambda v: v["jobs"].pop(3))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_one_stale_symbol_original_fails_after_reseal(self):
        self.edit_job_original(2, lambda v: v["data"]["items"][0].__setitem__(1, "20260930"))
        with self.assertRaisesRegex(ValueError, "STALE_NATIVE_SESSION"): f.review_capture(self.manifest_ref, self.plan)

    def test_wrong_session_summary_fails(self):
        self.edit_manifest(lambda v: v.update(session="2026-10-09"))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_wrong_symbol_raw_fails(self):
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(0, "600312.SH"))
        with self.assertRaisesRegex(ValueError, "SYMBOL_DRIFT"): f.review_capture(self.manifest_ref, self.plan)

    def test_duplicate_raw_ref_fails(self):
        def mutate(v):
            v["jobs"][2]["raw_ref"] = v["jobs"][1]["raw_ref"]; v["jobs"][2]["source_response_hash"] = v["jobs"][1]["source_response_hash"]
        self.edit_manifest(mutate)
        with self.assertRaisesRegex(ValueError, "RAW_DUPLICATE"): f.review_capture(self.manifest_ref, self.plan)

    def test_mutated_raw_after_review_rejected_before_append(self):
        raw = Path(json.loads(Path(self.manifest_ref["path"]).read_bytes())["jobs"][1]["raw_ref"]["path"])
        raw.write_bytes(raw.read_bytes() + b" ")
        with self.assertRaises(ValueError): f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        self.assertEqual(f.inspect_simulation_store(self.path), self.genesis)

    def test_forged_producer_row_count_fails(self):
        self.edit_manifest(lambda v: v["jobs"][1].update(row_count=2))
        with self.assertRaisesRegex(ValueError, "SUMMARY_NOT_ORIGINAL"): f.review_capture(self.manifest_ref, self.plan)

    def test_native_bool_price_rejected(self):
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(2, True))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_native_ohlc_conflict_rejected(self):
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(3, "1"))
        with self.assertRaisesRegex(ValueError, "OHLC_CONFLICT"): f.review_capture(self.manifest_ref, self.plan)

    def test_witness_without_eod_is_rejected(self):
        witness = json.loads(Path(self.plan["session_evidence_ref"]["path"]).read_bytes()); witness["eod_observed"] = False
        self.plan["session_evidence_ref"] = put(Path(self.plan["session_evidence_ref"]["path"]), witness)
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_unknown_status_cannot_be_promoted(self):
        self.edit_manifest(lambda v: v["status_unknowns"][0].update(state="NORMAL"))
        with self.assertRaisesRegex(ValueError, "UNKNOWN_STATUS_PROMOTION"): f.review_capture(self.manifest_ref, self.plan)

    def test_date_only_cannot_be_availability(self):
        self.edit_clock(lambda v: v.update(current_available_at="2026-10-08", current_available_precision="DATE_ONLY"))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_conflicting_clock_precision_rejected(self):
        self.edit_clock(lambda v: v.update(retrieved_precision="SECOND"))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_late_old_date_clock_rejected(self):
        self.edit_clock(lambda v: v.update(started_at="2026-10-07T07:01:00.123Z"))
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER_OR_FRESHNESS"): f.review_capture(self.manifest_ref, self.plan)

    def test_future_source_clock_rejected(self):
        self.edit_clock(lambda v: v.update(started_at="2026-10-08T08:01:00.123Z"))
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER_OR_FRESHNESS"): f.review_capture(self.manifest_ref, self.plan)

    def test_publication_midnight_imputation_forbidden(self):
        self.edit_clock(lambda v: v.update(published_at="2026-10-08T00:00:00+08:00", published_precision="SECOND"))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_current_capture_cannot_claim_historical_visibility(self):
        self.edit_clock(lambda v: v.update(historical_visibility_proven=True))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_wrong_strategy_hash_rejected(self):
        self.plan["bindings"]["strategy_hash"] = "sha256:" + "0" * 64
        self.plan["plan_hash"] = digest({k: v for k, v in self.plan.items() if k != "plan_hash"})
        with self.assertRaisesRegex(ValueError, "PLAN_BINDING_DRIFT"): f.review_capture(self.manifest_ref, self.plan)

    def test_wrong_source_schema_version_rejected(self):
        self.plan["source_schema_version"] = "NEXT_GUESSED_VERSION"
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_snapshot_policy_reseal_not_authority(self):
        value = copy.deepcopy(self.snapshot); value["body"]["expected_plan"]["bindings"]["policy_hash"] = "sha256:" + "0" * 64
        value.pop("content_hash"); value = seal(value)
        with self.assertRaises(ValueError): f.append_simulation_session(self.path, value, self.genesis["head_hash"])

    def test_simulation_append_counts_only_simulation(self):
        first = f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        self.assertEqual(first["simulated_accepted_session_count"], 1); self.assertEqual(first["actual_forward_days"], 0)
        self.assertEqual(first["namespace"], f.SIMULATION_NAMESPACE); self.assertFalse(first["safe_to_trade"])
        self.assertEqual(f.inspect_simulation_store(self.path), first)

    def test_per_response_hash_changes_do_not_break_series(self):
        first = f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        p, r = fixture(self.directory / "capture-two", "2026-10-09", "two", self.plan["snapshot_a_ref"])
        second = f.append_simulation_session(self.path, f.issue_simulation_snapshot(r, p), first["head_hash"])
        self.assertEqual(second["accepted_session_count"], 2); self.assertEqual(second["actual_forward_days"], 0)
        self.assertEqual(second["records"][0]["series_binding"], second["records"][1]["series_binding"])
        self.assertNotEqual(second["records"][0]["snapshot"]["body"]["raw_observation_hash"], second["records"][1]["snapshot"]["body"]["raw_observation_hash"])

    def test_duplicate_session_never_increments(self):
        first = f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SESSION"): f.append_simulation_session(self.path, self.snapshot, first["head_hash"])
        self.assertEqual(f.inspect_simulation_store(self.path), first)

    def test_stale_expected_head_never_increments(self):
        first = f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "STALE_EXPECTED_HEAD"): f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        self.assertEqual(f.inspect_simulation_store(self.path), first)

    def test_concurrent_same_head_exactly_one_acceptance(self):
        outcomes = []
        def run():
            try: f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"]); outcomes.append("PASS")
            except ValueError: outcomes.append("REJECT")
        threads = [threading.Thread(target=run) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(outcomes), ["PASS", "REJECT"])
        self.assertEqual(f.inspect_simulation_store(self.path)["accepted_session_count"], 1)

    def test_failure_chain_is_sanitized_and_separate(self):
        with self.assertRaises(ValueError): f.attempt_simulation_session(self.path, {"chat_text": "UNTRUSTED_PAYLOAD_NOT_RETAINED"}, self.genesis["head_hash"])
        result = f.inspect_simulation_store(self.path)
        self.assertEqual(result["accepted_session_count"], 0); self.assertEqual(result["failed_attempt_count"], 1)
        self.assertEqual(result["actual_forward_days"], 0); self.assertEqual(result["head_hash"], self.genesis["head_hash"])
        self.assertNotIn("UNTRUSTED_PAYLOAD_NOT_RETAINED", canonical(result).decode())

    def test_external_update_delete_insert_forbidden(self):
        conn = sqlite3.connect(self.path)
        for sql in ("UPDATE forward_metadata SET hash='changed'", "DELETE FROM forward_metadata", "INSERT INTO forward_failures VALUES(1,'x','x','x','{}')"):
            with self.assertRaises(sqlite3.DatabaseError): conn.execute(sql)
        conn.close(); self.assertEqual(f.inspect_simulation_store(self.path), self.genesis)

    def test_restart_fresh_process_reopens_originals(self):
        first = f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        result = subprocess.run([sys.executable, "-B", "-c", "from wave_h.forward import recover_simulation_store;import json,sys;r=recover_simulation_store(sys.argv[1]);print(json.dumps({'actual':r['actual_forward_days'],'sim':r['result']['simulated_accepted_session_count']}))", str(self.path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(json.loads(result.stdout), {"actual": 0, "sim": 1})
        self.assertEqual(f.inspect_simulation_store(self.path), first)

    def test_corrupted_schema_recovery_does_not_repair(self):
        conn = sqlite3.connect(self.path); conn.execute("DROP TRIGGER forward_metadata_no_update"); conn.commit(); conn.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "SCHEMA_OR_INTEGRITY"): f.recover_simulation_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_original_recovery_does_not_repair(self):
        f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        Path(self.manifest_ref["path"]).unlink(); before = self.path.read_bytes()
        with self.assertRaises(ValueError): f.recover_simulation_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_recovery_expected_head_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "RECOVERY_HEAD_MISMATCH"): f.recover_simulation_store(self.path, "sha256:" + "0" * 64)

    def test_exclusive_creation_preserves_existing_store(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError): f.create_simulation_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_namespace_suffix_separation(self):
        with self.assertRaisesRegex(ValueError, "PATH_OR_NAMESPACE"): f.create_simulation_store(self.directory / "fake.wave-h.actual.sqlite3")

    def test_cross_namespace_snapshot_promotion_rejected(self):
        value = copy.deepcopy(self.snapshot); value["kind"] = "ACTUAL_LOCAL_SNAPSHOT_B"; value["namespace"] = f.ACTUAL_NAMESPACE
        value.pop("content_hash"); value = seal(value)
        with self.assertRaisesRegex(ValueError, "NAMESPACE_PROMOTION"): f.append_simulation_session(self.path, value, self.genesis["head_hash"])

    def test_actual_store_calls_block_before_caller_file_io(self):
        calls = [lambda: f.create_actual_store("/NEVER_READ/or-create.wave-h.actual.sqlite3"), lambda: f.inspect_actual_store("/NEVER_READ/existing.wave-h.actual.sqlite3"),
                 lambda: f.recover_actual_store("/NEVER_READ/existing.wave-h.actual.sqlite3"),
                 lambda: f.append_actual_session("/NEVER_READ/existing.wave-h.actual.sqlite3", self.snapshot, {"role": "HUMAN_USER"}, self.genesis["head_hash"]),
                 lambda: f.attempt_actual_session("/NEVER_READ/existing.wave-h.actual.sqlite3", self.snapshot, {"role": "LLM"}, self.genesis["head_hash"])]
        with patch.object(f, "_path", side_effect=AssertionError("caller path inspected")):
            for call in calls:
                with self.assertRaisesRegex(ValueError, "NOT_ENROLLED"): call()

    def test_producer_self_approval_llm_fixture_handle_cannot_issue_actual(self):
        handles = [{"role": "HUMAN_USER", "approved": True}, {"role": "INDEPENDENT_REVIEWER", "content_hash": self.snapshot["content_hash"]}, {"role": "LLM", "conclusion": "APPROVE"}, object()]
        with patch.object(f, "reopen", side_effect=AssertionError("caller originals opened")):
            for handle in handles:
                with self.assertRaisesRegex(ValueError, "NOT_ENROLLED"): f.issue_snapshot_b(self.manifest_ref, self.plan, handle)

    def test_capture_marker_cannot_authorize_actual_forward(self):
        with self.assertRaisesRegex(ValueError, "NOT_ENROLLED"): f.append_actual_session("/not-created", self.snapshot, {"permissions": ["LOCAL_READ_ONLY_CAPTURE"]}, self.genesis["head_hash"])

    def test_all_trade_native_broker_cloud_paths_unconditionally_blocked(self):
        for entry in (f.issue_native, f.execute_trade, f.connect_broker, f.cloud_export):
            with self.assertRaises(ValueError): entry({"permissions": ["ACTUAL_FORWARD_NO_DECISION_APPEND"], "role": "HUMAN_USER", "approved": True})

    def test_persisted_forward_signed_expected_head_binding(self):
        actual_shape = copy.deepcopy(self.snapshot)
        actual_shape["body"]["signed_acceptance"] = {"body": {"issued_at": "2026-10-08T07:03:00Z"}}
        actual_shape.pop("content_hash"); actual_shape = seal(actual_shape)
        claims = {"bindings": bindings(), "session": "2026-10-08", "issued_at": "2026-10-08T07:04:00Z",
                  "scope": {"session": "2026-10-08", "snapshot_hash": actual_shape["content_hash"], "expected_head": self.genesis["head_hash"]}}
        # Pure binding checks here do not verify signatures or issue an actual handle.
        f._forward_bind(claims, actual_shape, self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "GRANT_EXPECTED_HEAD_DRIFT"): f._forward_bind(claims, actual_shape, "sha256:" + "0" * 64)
        self.assertEqual(f.inspect_simulation_store(self.path)["actual_forward_days"], 0)

    def test_original_resealing_invalidates_external_review_binding(self):
        original_request = f.review_capture(self.manifest_ref, self.plan)
        claims = {"bindings": bindings(), "session": original_request["session"], "issued_at": "2026-10-08T07:03:00Z",
                  "scope": {"capture_hash": original_request["capture_hash"], "capture_manifest_hash": original_request["capture_manifest_hash"],
                            "plan_hash": original_request["plan_hash"], "acceptance_request_hash": original_request["content_hash"],
                            "originals_digest": original_request["originals_digest"]}}
        # A pure binding check confers no cryptographic or actual authority.
        f._review_bind(claims, original_request)
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(5, "20"))
        updated_request = f.review_capture(self.manifest_ref, self.plan)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_ACCEPTANCE_BINDING_DRIFT"): f._review_bind(claims, updated_request)

    def test_wrong_snapshot_a_original_hash_rejected(self):
        a = json.loads(Path(self.plan["snapshot_a_ref"]["path"]).read_bytes()); a["raw_observation_hash"] = "sha256:" + "0" * 64
        Path(self.plan["snapshot_a_ref"]["path"]).write_bytes(canonical(a))
        with self.assertRaises(ValueError): f.review_capture(self.manifest_ref, self.plan)

    def test_policy_hash_change_rejected_even_plan_resealed(self):
        self.plan["bindings"]["policy_hash"] = "sha256:" + "0" * 64
        self.plan["plan_hash"] = digest({k: v for k, v in self.plan.items() if k != "plan_hash"})
        with self.assertRaisesRegex(ValueError, "PLAN_BINDING_DRIFT"): f.review_capture(self.manifest_ref, self.plan)

    def test_job_unit_change_rejected_even_plan_resealed(self):
        self.plan["jobs"][1]["units"]["vol"] = "CNY"
        self.plan["plan_hash"] = digest({k: v for k, v in self.plan.items() if k != "plan_hash"})
        with self.assertRaisesRegex(ValueError, "JOB_POLICY_SCOPE_DRIFT"): f.review_capture(self.manifest_ref, self.plan)

    def test_transaction_failure_rolls_back_without_advance(self):
        original_inspect = f._inspect
        calls = 0
        def crash_after_insert(*args):
            nonlocal calls
            calls += 1
            if calls == 2: raise RuntimeError("SIMULATED_PROCESS_FAILURE_AFTER_INSERT_BEFORE_COMMIT")
            return original_inspect(*args)
        with patch.object(f, "_inspect", side_effect=crash_after_insert):
            with self.assertRaises(RuntimeError): f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])
        self.assertEqual(f.inspect_simulation_store(self.path), self.genesis)
        self.assertEqual(f.append_simulation_session(self.path, self.snapshot, self.genesis["head_hash"])["simulated_accepted_session_count"], 1)

    def test_native_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            f._parse_original(self.plan["jobs"][1], b'{"code":0,"code":0,"msg":null,"data":null}', self.plan["session"])

    def test_native_scientific_price_literal_not_silently_rounded(self):
        raw = native("daily", SYMBOLS[0], self.plan["session"])
        raw = raw.replace(b'"10"', b'1e1', 1)
        with self.assertRaises(ValueError): f._parse_original(self.plan["jobs"][1], raw, self.plan["session"])

    def test_basic_wrong_exchange_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(3, "SZSE"))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_wrong_currency_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(4, "USD"))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_mismatched_symbol_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(1, "600312"))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_empty_name_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(2, ""))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_nonstring_name_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(2, True))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_unknown_list_status_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(5, "UNKNOWN"))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_noncalendar_listing_date_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(6, "20260230"))
        with self.assertRaisesRegex(ValueError, "SESSION_DATE_REQUIRED"): f.review_capture(self.manifest_ref, self.plan)

    def test_basic_wrong_delisting_date_type_original_resealed_still_rejected(self):
        self.edit_job_original(4, lambda v: v["data"]["items"][0].__setitem__(7, 20261008))
        with self.assertRaisesRegex(ValueError, "SECURITY_BASIC_DATE_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_suspension_invalid_event_enum_original_resealed_still_rejected(self):
        self.edit_job_original(7, lambda v: v["data"].update(items=[[SYMBOLS[0], "20261008", "SYNTHETIC_TIMING", "UNKNOWN"]]))
        with self.assertRaisesRegex(ValueError, "SUSPENSION_EVENT_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_suspension_nonstring_timing_original_resealed_still_rejected(self):
        self.edit_job_original(7, lambda v: v["data"].update(items=[[SYMBOLS[0], "20261008", 0, "S"]]))
        with self.assertRaisesRegex(ValueError, "SUSPENSION_EVENT_SCHEMA_INVALID"): f.review_capture(self.manifest_ref, self.plan)

    def test_daily_nonpositive_preclose_original_resealed_still_rejected(self):
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(6, "0"))
        with self.assertRaisesRegex(ValueError, "NATIVE_DECIMAL_RANGE"): f.review_capture(self.manifest_ref, self.plan)

    def test_daily_negative_preclose_original_resealed_still_rejected(self):
        self.edit_job_original(1, lambda v: v["data"]["items"][0].__setitem__(6, "-1"))
        with self.assertRaisesRegex(ValueError, "NATIVE_DECIMAL_RANGE"): f.review_capture(self.manifest_ref, self.plan)

    def test_witness_source_invalid_original_resealed_still_rejected(self):
        original = json.loads(Path(self.plan["session_evidence_ref"]["path"]).read_bytes())
        for invalid in ("", None, True, "X" * 161):
            witness = dict(original, witness_source=invalid)
            self.plan["session_evidence_ref"] = put(Path(self.plan["session_evidence_ref"]["path"]), witness)
            self.plan["plan_hash"] = digest({k: v for k, v in self.plan.items() if k != "plan_hash"})
            self.edit_manifest(lambda v: v.update(plan=copy.deepcopy(self.plan), plan_hash=self.plan["plan_hash"], source_session_evidence_ref=self.plan["session_evidence_ref"]))
            with self.assertRaisesRegex(ValueError, "WITNESS_SOURCE_REQUIRED"): f.review_capture(self.manifest_ref, self.plan)

    def test_snapshot_a_capture_id_invalid_original_resealed_still_rejected(self):
        original = json.loads(Path(self.plan["snapshot_a_ref"]["path"]).read_bytes())
        for invalid in ("", "X" * 161):
            anchor = dict(original, capture_id=invalid)
            self.plan["snapshot_a_ref"] = put(Path(self.plan["snapshot_a_ref"]["path"]), anchor)
            self.plan["plan_hash"] = digest({k: v for k, v in self.plan.items() if k != "plan_hash"})
            self.edit_manifest(lambda v: v.update(plan=copy.deepcopy(self.plan), plan_hash=self.plan["plan_hash"], snapshot_a_ref=self.plan["snapshot_a_ref"]))
            with self.assertRaisesRegex(ValueError, "REFERENCE_A_CAPTURE_ID_REQUIRED"): f.review_capture(self.manifest_ref, self.plan)


if __name__ == "__main__": unittest.main()
