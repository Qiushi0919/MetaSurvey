"""SYNTHETIC_NOT_OWNER_POLICY fixture-only durable Forward boundary checks."""

import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from post_wave_e import forward as f
from post_wave_e.common import SYMBOLS, VERSION, UNSET, canonical, digest


def evidence(day="2026-10-08", authorization_id="fixture:synthetic-owner"):
    stamp = lambda clock: day + "T" + clock + ".000000000+08:00"
    common = {"scope": "FIXTURE_ONLY", "namespace": f.NAMESPACE, "account_namespace": f.ACCOUNT, "strategy_namespace": f.STRATEGY, "mode": f.MODE, "schema_version": VERSION, "observed_universe": list(SYMBOLS)}
    snapshot = lambda source_day, marker: {"kind": "SYNTHETIC_SNAPSHOT", "namespace": f.NAMESPACE, "version": VERSION, "source_day": source_day, "content_hash": digest({"provenance": "SYNTHETIC_NOT_OWNER_POLICY", "marker": marker})}
    return dict(common, kind="SYNTHETIC_SOURCE_OBSERVATION", source_day=day, calendar_session={"kind": "SYNTHETIC_OPEN_SESSION", "venue": "SSE", "source_ref": "fixture://calendar/" + day, "session_day": day, "market_close": stamp("15:00:00")}, event_time=stamp("15:00:00"), published_at=stamp("16:00:00"), available_at=stamp("16:30:00"), retrieved_at=stamp("17:00:00"), decision_cutoff=stamp("18:00:00"), authorization={"subject": "SYNTHETIC_HUMAN_USER", "authorization_id": authorization_id, "issued_at": stamp("09:00:00"), "expires_at": stamp("23:00:00")}, snapshot_a=snapshot("2026-09-30", "synthetic-anchor"), snapshot_b=snapshot(day, "synthetic-fresh-" + day), bindings={key: digest({"provenance": "SYNTHETIC_NOT_OWNER_POLICY", "key": key}) for key in f._BINDINGS})


def record(ev, key="fixture:no-decision"):
    value = {key: copy.deepcopy(ev[key]) for key in f._COMMON}
    value.update({key: copy.deepcopy(ev[key]) for key in ("source_day", "decision_cutoff", "snapshot_a", "snapshot_b", "bindings")})
    value.update(kind="FORWARD_PAPER_FIXTURE_RECORD", source_clocks={key: ev[key] for key in f._CLOCKS}, decision="NO_DECISION", tradeability="UNKNOWN", actual_policies={key: UNSET for key in ("account", "cost", "risk", "strategy")}, unknowns=sorted(f._UNKNOWNS), reason_codes=sorted(f._REASONS), idempotency_key=key)
    return value


class DurableForward(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name).resolve()
        self.path = self.directory / "paper.fixture.sqlite3"
        self.empty = f.create_fixture_store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def append(self, day="2026-10-08", key="fixture:day1", head=None):
        ev = evidence(day)
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        return f.append_fixture_record(self.path, authority, record(ev, key), head or f.inspect_fixture_store(self.path)["head_hash"])

    def rejects_evidence(self, change, reason=None):
        ev = evidence()
        change(ev)
        with self.assertRaisesRegex(ValueError, reason or "FORWARD|PREP"):
            f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)

    def rejects_record(self, change, reason=None):
        path = self.directory / (uuid.uuid4().hex + ".fixture.sqlite3")
        empty = f.create_fixture_store(path)
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        value = record(ev)
        change(value)
        with self.assertRaisesRegex(ValueError, reason or "FORWARD|PREP"):
            f.append_fixture_record(path, authority, value, empty["head_hash"])
        self.assertEqual(f.inspect_fixture_store(path), empty)
        good = f.append_fixture_record(path, authority, record(ev), empty["head_hash"])
        self.assertEqual(good["fixture_day_count"], 1)

    def test_empty_private_store_has_no_native_tables(self):
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        self.assertEqual(self.empty["actual_forward_days"], 0)
        self.assertEqual(self.empty["fixture_day_count"], 0)
        conn = sqlite3.connect(self.path)
        self.assertEqual({item[0] for item in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}, {"fixture_metadata", "fixture_records"})
        conn.close()

    def test_persistence_reopen_keeps_chain_and_zero_actual_days(self):
        first = self.append()
        second = self.append("2026-10-09", "fixture:day2")
        self.assertEqual(second, f.inspect_fixture_store(str(self.path)))
        self.assertEqual(second["records"][1]["predecessor_hash"], first["head_hash"])
        self.assertEqual(second["fixture_day_count"], 2)
        self.assertEqual(second["actual_forward_days"], 0)
        self.assertEqual(second["snapshot_authority"], "DISPLAY_ONLY")
        self.assertFalse(second["native_promotion"])

    def test_readonly_reopen_survives_new_interpreter(self):
        result = self.append()
        code = "import json,sys; from post_wave_e.forward import inspect_fixture_store; print(json.dumps(inspect_fixture_store(sys.argv[1]),sort_keys=True))"
        proc = subprocess.run([sys.executable, "-B", "-c", code, str(self.path)], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout), result)

    def test_display_copy_mutation_does_not_change_store(self):
        self.append()
        result = f.inspect_fixture_store(self.path)
        result["records"][0]["record"]["decision"] = "BUY"
        result["actual_forward_days"] = 1
        again = f.inspect_fixture_store(self.path)
        self.assertEqual(again["records"][0]["record"]["decision"], "NO_DECISION")
        self.assertEqual(again["actual_forward_days"], 0)

    def test_store_copy_cannot_rebind_path(self):
        self.append()
        copied = self.directory / "copied.fixture.sqlite3"
        shutil.copy2(self.path, copied)
        with self.assertRaisesRegex(ValueError, "FORWARD_STORE_BINDING_DRIFT"):
            f.inspect_fixture_store(copied)

    def test_symlink_store_rejected(self):
        target = self.directory / "link.fixture.sqlite3"
        target.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "FORWARD_PATH_INVALID"):
            f.inspect_fixture_store(target)

    def test_nonprivate_file_rejected(self):
        os.chmod(self.path, 0o644)
        with self.assertRaisesRegex(ValueError, "FORWARD_PRIVATE_STORE_REQUIRED"):
            f.inspect_fixture_store(self.path)

    def test_nonprivate_parent_rejected(self):
        public = self.directory / "public"
        public.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError, "FORWARD_PRIVATE_DIRECTORY_REQUIRED"):
            f.create_fixture_store(public / "paper.fixture.sqlite3")

    def test_arbitrary_database_and_relative_path_rejected(self):
        for path in ("relative.fixture.sqlite3", self.directory / "actual.sqlite3"):
            with self.subTest(path=str(path)), self.assertRaisesRegex(ValueError, "FORWARD_PATH_INVALID"):
                f.create_fixture_store(path)

    def test_existing_store_is_never_overwritten(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "FORWARD_STORE_ALREADY_EXISTS"):
            f.create_fixture_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_sql_update_delete_guards(self):
        self.append()
        conn = sqlite3.connect(self.path)
        for sql in ("DELETE FROM fixture_records", "UPDATE fixture_records SET source_day='2026-10-09'", "DELETE FROM fixture_metadata", "UPDATE fixture_metadata SET metadata_hash='forged'"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                conn.execute(sql)
            conn.rollback()
        conn.close()
        self.assertEqual(f.inspect_fixture_store(self.path)["fixture_day_count"], 1)

    def test_direct_sql_insert_without_capability_rejected(self):
        conn = sqlite3.connect(self.path)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("INSERT INTO fixture_records VALUES(1,'2026-10-08','fixture:k','fixture:a','h','d','{}')")
        conn.rollback()
        conn.close()
        self.assertEqual(f.inspect_fixture_store(self.path), self.empty)

    def test_dropped_guard_detected_on_reopen(self):
        conn = sqlite3.connect(self.path)
        conn.execute("DROP TRIGGER fixture_records_no_update")
        conn.close()
        with self.assertRaisesRegex(ValueError, "FORWARD_STORE_SCHEMA_DRIFT"):
            f.inspect_fixture_store(self.path)

    def test_body_tamper_detected_even_after_guard_restoration(self):
        self.append()
        conn = sqlite3.connect(self.path)
        conn.execute("DROP TRIGGER fixture_records_no_update")
        item = json.loads(conn.execute("SELECT body_json FROM fixture_records").fetchone()[0])
        item["predecessor_hash"] = digest({"provenance": "SYNTHETIC_FORGERY"})
        conn.execute("UPDATE fixture_records SET body_json=?", (canonical(item).decode(),))
        conn.execute(f._TRIGGERS["fixture_records_no_update"])
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, "FORWARD_CHAIN_HASH_OR_SEQUENCE_INVALID"):
            f.inspect_fixture_store(self.path)

    def test_column_tamper_detected(self):
        self.append()
        conn = sqlite3.connect(self.path)
        conn.execute("DROP TRIGGER fixture_records_no_update")
        conn.execute("UPDATE fixture_records SET idempotency_key='fixture:forged'")
        conn.execute(f._TRIGGERS["fixture_records_no_update"])
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, "FORWARD_STORE_COLUMN_DRIFT"):
            f.inspect_fixture_store(self.path)

    def test_stale_head_rejected_without_consuming_authority(self):
        self.append()
        ev = evidence("2026-10-09")
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        value = record(ev, "fixture:day2")
        with self.assertRaisesRegex(ValueError, "FORWARD_STALE_HEAD_CONFLICT"):
            f.append_fixture_record(self.path, authority, value, self.empty["head_hash"])
        result = f.append_fixture_record(self.path, authority, value, f.inspect_fixture_store(self.path)["head_hash"])
        self.assertEqual(result["fixture_day_count"], 2)

    def test_duplicate_day_rejected(self):
        self.append()
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        with self.assertRaisesRegex(ValueError, "FORWARD_DUPLICATE_DAY"):
            f.append_fixture_record(self.path, authority, record(ev, "fixture:other-key"), f.inspect_fixture_store(self.path)["head_hash"])
        self.assertEqual(f.inspect_fixture_store(self.path)["fixture_day_count"], 1)

    def test_duplicate_key_across_days_rejected(self):
        self.append(key="fixture:repeat")
        ev = evidence("2026-10-09")
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        with self.assertRaisesRegex(ValueError, "FORWARD_DUPLICATE_IDEMPOTENCY_KEY"):
            f.append_fixture_record(self.path, authority, record(ev, "fixture:repeat"), f.inspect_fixture_store(self.path)["head_hash"])

    def test_past_session_cannot_append_after_later_day(self):
        self.append("2026-10-09")
        ev = evidence("2026-10-08")
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        with self.assertRaisesRegex(ValueError, "FORWARD_DAY_ORDER_INVALID"):
            f.append_fixture_record(self.path, authority, record(ev, "fixture:earlier"), f.inspect_fixture_store(self.path)["head_hash"])

    def test_transaction_failure_rolls_back_insert_and_capability_use(self):
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        original = f._chain
        calls = []
        def fail_after_insert(conn, path):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError("SYNTHETIC_COMMIT_FAILURE")
            return original(conn, path)
        with patch.object(f, "_chain", fail_after_insert), self.assertRaisesRegex(ValueError, "SYNTHETIC_COMMIT_FAILURE"):
            f.append_fixture_record(self.path, authority, record(ev), self.empty["head_hash"])
        self.assertEqual(f.inspect_fixture_store(self.path), self.empty)
        result = f.append_fixture_record(self.path, authority, record(ev), self.empty["head_hash"])
        self.assertEqual(result["fixture_day_count"], 1)

    def test_concurrent_same_head_has_one_winner_no_fork(self):
        ev = evidence()
        authorities = [f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev) for _ in range(2)]
        def attempt(index):
            try:
                f.append_fixture_record(self.path, authorities[index], record(ev, "fixture:concurrent-" + str(index)), self.empty["head_hash"])
                return "COMMITTED"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(attempt, [0, 1]))
        self.assertEqual(sorted(result), ["COMMITTED", "FORWARD_STALE_HEAD_CONFLICT"])
        self.assertEqual(f.inspect_fixture_store(self.path)["fixture_day_count"], 1)

    def test_authority_can_only_be_used_once_even_in_second_store(self):
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        f.append_fixture_record(self.path, authority, record(ev), self.empty["head_hash"])
        other = self.directory / "other.fixture.sqlite3"
        empty = f.create_fixture_store(other)
        with self.assertRaisesRegex(ValueError, "FORWARD_AUTHORITY_ALREADY_USED"):
            f.append_fixture_record(other, authority, record(ev), empty["head_hash"])

    def test_copied_authority_rejected(self):
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        with self.assertRaisesRegex(ValueError, "FORWARD_AUTHORITY_IDENTITY_OR_SEAL_INVALID"):
            f.append_fixture_record(self.path, copy.deepcopy(authority), record(ev), self.empty["head_hash"])

    def test_directly_constructed_authority_rejected(self):
        ev = evidence()
        genuine = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        authority = f.FixtureAuthority(genuine.authority_id, copy.deepcopy(genuine._body))
        with self.assertRaisesRegex(ValueError, "FORWARD_AUTHORITY_IDENTITY_OR_SEAL_INVALID"):
            f.append_fixture_record(self.path, authority, record(ev), self.empty["head_hash"])

    def test_authority_body_mutation_rejected(self):
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        authority._body["actual_forward_days"] = 1
        with self.assertRaisesRegex(ValueError, "FORWARD_AUTHORITY_IDENTITY_OR_SEAL_INVALID"):
            f.append_fixture_record(self.path, authority, record(ev), self.empty["head_hash"])

    def test_llm_or_generic_human_cannot_issue(self):
        for kind in ("LLM", "LLM_APPROVE", "APPROVE", "HUMAN_USER", True, None):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "FORWARD_SYNTHETIC_HUMAN_REQUIRED"):
                f.issue_fixture_authority(kind, evidence())
        self.rejects_evidence(lambda ev: ev["authorization"].update(subject="HUMAN_OWNER"), "FORWARD_SYNTHETIC_HUMAN_REQUIRED")

    def test_actual_source_or_mode_promotion_rejected(self):
        self.rejects_evidence(lambda ev: ev.update(kind="SOURCE_OBSERVATION"))
        self.rejects_evidence(lambda ev: ev.update(mode="PAPER"), "FORWARD_MODE_PROMOTION_FORBIDDEN")
        self.rejects_record(lambda rec: rec.update(mode="PRODUCTION"), "FORWARD_MODE_PROMOTION_FORBIDDEN")

    def test_account_strategy_namespace_isolation(self):
        self.rejects_record(lambda rec: rec.update(account_namespace="REAL_ACCOUNT"), "FORWARD_ACCOUNT_DRIFT")
        self.rejects_record(lambda rec: rec.update(strategy_namespace="EVENT_3"), "FORWARD_STRATEGY_DRIFT")
        self.rejects_record(lambda rec: rec.update(namespace="LOCAL_FORWARD_PAPER_FIXTURE:RESEARCH_6_18M"), "FORWARD_NAMESPACE_DRIFT")

    def test_exact_universe_and_version(self):
        self.rejects_evidence(lambda ev: ev.update(observed_universe=ev["observed_universe"][::-1]), "FORWARD_UNIVERSE_DRIFT")
        self.rejects_record(lambda rec: rec.update(schema_version="2.0.0"), "FORWARD_VERSION_DRIFT")

    def test_holiday_weekend_or_anchor_cannot_be_fresh_session(self):
        for day in ("2026-09-30", "2026-10-06", "2026-10-10", "2026-10-11"):
            with self.subTest(day=day), self.assertRaisesRegex(ValueError, "FORWARD_SOURCE_NOT_FRESH|FORWARD_FIXTURE_SESSION_CLOSED"):
                f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", evidence(day))

    def test_date_only_naive_utc_and_midnight_rejected(self):
        for value in ("2026-10-08", "2026-10-08T18:00:00", "2026-10-08T10:00:00.000000000Z", "2026-10-08T00:00:00.000000000+08:00", "2026-10-08T18:00:00.000+08:00"):
            with self.subTest(value=value):
                self.rejects_evidence(lambda ev: ev.update(decision_cutoff=value))

    def test_nanosecond_visibility_order_is_not_truncated(self):
        self.rejects_evidence(lambda ev: ev.update(available_at="2026-10-08T17:00:00.000000001+08:00", retrieved_at="2026-10-08T17:00:00.000000000+08:00"), "FORWARD_CLOCK_ORDER_INVALID")

    def test_clock_days_and_bar_close_binding(self):
        self.rejects_evidence(lambda ev: ev.update(published_at="2026-10-09T16:00:00.000000000+08:00"), "FORWARD_CLOCK_DAY_DRIFT")
        self.rejects_evidence(lambda ev: ev.update(event_time="2026-10-08T14:59:59.999999999+08:00"), "FORWARD_BAR_EVENT_INVALID")
        self.rejects_evidence(lambda ev: ev["calendar_session"].update(market_close="2026-10-08T15:00:00.000000001+08:00"), "FORWARD_SESSION_CLOSE_INVALID")

    def test_publication_before_eod_close_blocked(self):
        self.rejects_evidence(lambda ev: ev.update(published_at="2026-10-08T14:59:00.000000000+08:00"), "FORWARD_CLOCK_ORDER_INVALID")

    def test_synthetic_authorization_expiry_and_future_issue(self):
        self.rejects_evidence(lambda ev: ev["authorization"].update(expires_at=ev["decision_cutoff"]), "FORWARD_AUTHORITY_EXPIRED_OR_FUTURE")
        self.rejects_evidence(lambda ev: ev["authorization"].update(issued_at="2026-10-08T18:00:00.000000001+08:00"), "FORWARD_AUTHORITY_EXPIRED_OR_FUTURE")

    def test_snapshot_b_stale_or_cross_namespace_rejected(self):
        self.rejects_evidence(lambda ev: ev["snapshot_b"].update(content_hash=ev["snapshot_a"]["content_hash"]), "FORWARD_SNAPSHOT_NOT_FRESH")
        self.rejects_evidence(lambda ev: ev["snapshot_b"].update(source_day="2026-09-30"), "FORWARD_SNAPSHOT_BINDING_INVALID")
        self.rejects_record(lambda rec: rec["snapshot_b"].update(namespace="CORE_40"), "FORWARD_RECORD_AUTHORITY_BINDING_DRIFT")

    def test_record_source_hash_and_clock_mutation_rejected(self):
        self.rejects_record(lambda rec: rec["bindings"].update(source_hash=digest({"provenance": "SYNTHETIC_FORGERY"})), "FORWARD_RECORD_AUTHORITY_BINDING_DRIFT")
        self.rejects_record(lambda rec: rec["source_clocks"].update(available_at="2026-10-08T16:00:00.000000000+08:00"), "FORWARD_RECORD_CLOCK_BINDING_DRIFT")

    def test_unknown_config_and_tradeability_cannot_be_erased(self):
        self.rejects_record(lambda rec: rec.update(tradeability="TRADEABLE"), "FORWARD_TRADEABILITY_PROMOTION_FORBIDDEN")
        self.rejects_record(lambda rec: rec["actual_policies"].update(cost="SYNTHETIC_COMMISSION"), "FORWARD_OWNER_POLICY_PROMOTION_FORBIDDEN")
        self.rejects_record(lambda rec: rec.update(unknowns=[]), "FORWARD_UNKNOWN_OR_REASON_ERASURE")
        self.rejects_record(lambda rec: rec.update(reason_codes=[]), "FORWARD_UNKNOWN_OR_REASON_ERASURE")

    def test_no_candidate_order_fill_or_same_bar_interface(self):
        for key in ("candidate", "signal", "approval", "order_intent", "fill", "hypothetical_fill", "same_bar_fill", "t_plus_one_override"):
            with self.subTest(key=key):
                self.rejects_record(lambda rec: rec.update({key: {"kind": "SYNTHETIC_FORGERY"}}), "FORWARD_RECORD_SHAPE_INVALID")
        self.rejects_record(lambda rec: rec.update(decision="BUY"), "FORWARD_NATIVE_DECISION_FORBIDDEN")

    def test_no_actual_day_boolean_or_counter_import(self):
        for key in ("actual_forward_days", "productionGate", "owner_approved", "historical_visibility_proven", "native_promotion"):
            with self.subTest(key=key):
                self.rejects_record(lambda rec: rec.update({key: True}), "FORWARD_RECORD_SHAPE_INVALID")

    def test_float_boolean_hash_and_duplicate_reasons_rejected(self):
        self.rejects_record(lambda rec: rec.update(idempotency_key=1.0), "PREP_NON_JSON_OR_FLOAT")
        self.rejects_evidence(lambda ev: ev["bindings"].update(source_hash=True), "PREP_HASH_INVALID")
        self.rejects_record(lambda rec: rec["reason_codes"].append(rec["reason_codes"][0]), "FORWARD_UNKNOWN_OR_REASON_ERASURE")

    def test_readiness_never_conveys_actual_authority(self):
        r = f.readiness()
        self.assertEqual(r["real_start_state"], "BLOCKED")
        self.assertEqual(r["actual_forward_days"], 0)
        self.assertFalse(r["native_promotion"])
        self.assertFalse(r["historical_visibility_proven"])
        self.assertFalse(r["scheduling_enabled"])
        self.assertFalse(r["hypothetical_fill_support"])
        self.assertEqual(r["actual_settings"], UNSET)
        self.assertEqual(r["real_authority_issuance"], "UNAVAILABLE_THIS_WAVE")

    def test_real_entry_unconditionally_rejects_all_receipts_and_booleans(self):
        ev = evidence()
        authority = f.issue_fixture_authority("SYNTHETIC_HUMAN_USER", ev)
        probes = [{}, {"owner_approved": True}, {"kind": "HUMAN_USER", "approval": "APPROVE"}, {"source_admitted": True, "historical_visibility_proven": True}, {"authority": authority, "path": self.path}, {"record": record(ev), "receipt": f.inspect_fixture_store(self.path)}]
        for probe in probes:
            with self.subTest(keys=list(probe)), self.assertRaisesRegex(ValueError, "REAL_FORWARD_NOT_AUTHORIZED"):
                f.run_real_forward(**probe)


if __name__ == "__main__":
    unittest.main()
