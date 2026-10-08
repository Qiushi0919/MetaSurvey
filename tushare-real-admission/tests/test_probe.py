"""Offline synthetic sentinel/rows only: no real credentials, network or raw evidence."""
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "probe.py"
module_spec = importlib.util.spec_from_file_location("real_admission_probe_under_test", PATH)
probe = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = probe
module_spec.loader.exec_module(probe)
MARKER = "SYNTHETIC_NON_SECRET_RUNTIME_12345"
NOW = "2026-10-05T18:00:00.123456Z"

def request(api="daily", stage="SMOKE"):
    return next(s for s in probe.build_plan(stage) if s.api_name == api and dict(s.params).get("ts_code", "603993.SH") == "603993.SH")

def raw(spec, rows=None, **changes):
    row = {key: None for key in spec.fields}
    row.update(ts_code="603993.SH", symbol="603993", trade_date="20260930", exchange="SSE", cal_date="20260930", is_open="1",
        pretrade_date="20260929", list_status="L", curr_type="CNY", open="10.1", high="10.8", low="10.0",
        close="10.3", pre_close="10.2", vol="100.5", amount="103.5", adj_factor="1.01", end_date="20260630",
        ann_date="20260830", update_flag="1", is_new="Y", in_date="20230101", suspend_type="S")
    row.update(changes)
    rows = [row] if rows is None else rows
    return json.dumps({"code": 0, "msg": "", "data": {"fields": list(spec.fields), "items": [[r.get(k) for k in spec.fields] for r in rows]}}).encode()

class FakeTime:
    def __init__(self): self.value = 0
    def monotonic(self): return self.value
    def sleep(self, value): self.value += value

class ProbeTests(unittest.TestCase):
    def reason(self, expected, callback):
        with self.assertRaises(probe.ProbeError) as error: callback()
        self.assertEqual(str(error.exception), expected)

    def synthetic(self, specs=None, data=None, credential=True):
        specs = specs or [request()]
        tm = FakeTime()
        return probe.run_synthetic_probe(credential=probe.Credential(MARKER) if credential else None,
            plan=specs, transport=lambda spec, _: (200, data if data is not None else raw(spec)),
            clock=lambda: NOW, monotonic=tm.monotonic, sleeper=tm.sleep)

    def test_no_secret_blocks_before_transport_and_does_not_claim_rotation_needed(self):
        with patch.object(probe, "_live_transport", side_effect=AssertionError("NO_NETWORK")):
            report = probe.run_probe(credential=None, run_id="no-secret-test")
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(len(report["requests"]), 22)
        self.assertFalse(report["credential_rotation_required"])
        self.assertEqual(report["owner_asserted_expiration_date"], "2026-11-05")
        self.assertTrue(all(r["raw_sha256"] is None for r in report["requests"]))

    def test_keychain_success_native_bytes_no_secret_reference_in_metadata(self):
        calls = []
        def fake(service, account):
            calls.append((service, account))
            return 0, MARKER.encode()
        credential, lookup = probe.lookup_credential(native_getter=fake)
        self.assertIs(type(credential), probe.Credential)
        self.assertEqual(lookup["lookup_result"], "FOUND")
        self.assertEqual(calls, [(probe.KEYCHAIN_SERVICE, probe.KEYCHAIN_ACCOUNT)])
        self.assertNotIn(MARKER, json.dumps(lookup) + str(credential) + repr(credential) + repr(calls))

    def test_keychain_missing_and_errors_fixed_reasons_no_fallback(self):
        for status, expected in ((-25300, "KEYCHAIN_ITEM_NOT_FOUND"), (-25293, "KEYCHAIN_LOOKUP_FAILED")):
            fake = lambda *_args: (status, MARKER.encode())
            credential, lookup = probe.lookup_credential(native_getter=fake)
            self.assertIsNone(credential); self.assertEqual(lookup["lookup_result"], expected)
            self.assertNotIn(MARKER, json.dumps(lookup))

    def native_framework(self, status=0, payload=MARKER.encode(), size=None, fail=False):
        """Synthetic RAM buffer only; never load or call a real Security API."""
        buffer = probe.ctypes.create_string_buffer(payload)
        calls = []
        class Function:
            def __init__(self, callback): self.callback = callback
            def __call__(self, *args): return self.callback(*args)
        def find(*args):
            calls.append(("find", args[1], args[2], args[3], args[4]))
            probe.ctypes.cast(args[5], probe.ctypes.POINTER(probe.ctypes.c_uint32))[0] = len(payload) if size is None else size
            probe.ctypes.cast(args[6], probe.ctypes.POINTER(probe.ctypes.c_void_p))[0] = probe.ctypes.addressof(buffer)
            if fail: raise RuntimeError(MARKER)
            return status
        def release(attributes, content):
            calls.append(("free", attributes, bool(content.value)))
            return 0
        framework = type("Framework", (), {})()
        framework.SecKeychainFindGenericPassword = Function(find)
        framework.SecKeychainItemFreeContent = Function(release)
        return framework, calls

    def test_default_native_security_signature_exact_reference_and_free(self):
        framework, calls = self.native_framework()
        with patch.object(probe.ctypes, "CDLL", return_value=framework) as loader:
            credential, lookup = probe.lookup_credential()
        self.assertIs(type(credential), probe.Credential)
        self.assertEqual(lookup["lookup_result"], "FOUND")
        loader.assert_called_once_with("/System/Library/Frameworks/Security.framework/Security")
        self.assertEqual(calls, [("find", len(probe.KEYCHAIN_SERVICE), probe.KEYCHAIN_SERVICE.encode(), len(probe.KEYCHAIN_ACCOUNT), probe.KEYCHAIN_ACCOUNT.encode()), ("free", None, True)])
        self.assertEqual(len(framework.SecKeychainFindGenericPassword.argtypes), 8)
        self.assertIs(framework.SecKeychainFindGenericPassword.restype, probe.ctypes.c_int32)
        self.assertNotIn(MARKER, json.dumps(lookup) + repr(calls))

    def test_native_free_on_find_error_status_exception_oversize_and_decode_error(self):
        cases = [({"status": -25300}, "KEYCHAIN_ITEM_NOT_FOUND"), ({"status": -25293}, "KEYCHAIN_LOOKUP_FAILED"),
            ({"fail": True}, "KEYCHAIN_LOOKUP_FAILED"), ({"size": 4097}, "KEYCHAIN_LOOKUP_FAILED"),
            ({"payload": b"\xff"}, "KEYCHAIN_LOOKUP_FAILED"), ({"payload": b""}, "KEYCHAIN_EMPTY")]
        for kwargs, expected in cases:
            framework, calls = self.native_framework(**kwargs)
            with patch.object(probe.ctypes, "CDLL", return_value=framework):
                credential, lookup = probe.lookup_credential()
            self.assertIsNone(credential)
            self.assertEqual(lookup["lookup_result"], expected)
            self.assertEqual(calls[-1], ("free", None, True))
            self.assertNotIn(MARKER, json.dumps(lookup))

    def test_native_load_failure_has_no_cli_fallback_and_fixed_reason(self):
        with patch.object(probe.ctypes, "CDLL", side_effect=RuntimeError(MARKER)) as loader:
            credential, lookup = probe.lookup_credential()
        self.assertIsNone(credential)
        self.assertEqual(lookup["lookup_result"], "KEYCHAIN_LOOKUP_FAILED")
        loader.assert_called_once()
        self.assertNotIn(MARKER, json.dumps(lookup))

    def test_native_getter_bad_return_types_and_failures_do_not_escape(self):
        for result in ((True, MARKER.encode()), (0, MARKER), (0, b"x" * 4097), (0, b"\xff"), (0, b"")):
            credential, lookup = probe.lookup_credential(native_getter=lambda *_: result)
            self.assertIsNone(credential)
            self.assertNotIn(MARKER, json.dumps(lookup))
        def failure(*_): raise RuntimeError(MARKER)
        credential, lookup = probe.lookup_credential(native_getter=failure)
        self.assertIsNone(credential)
        self.assertEqual(lookup["lookup_result"], "KEYCHAIN_LOOKUP_FAILED")

    def test_exact_credential_type_and_immutability(self):
        credential = probe.Credential(MARKER)
        self.reason("CREDENTIAL_IMMUTABLE", lambda: setattr(credential, "_value", "different"))
        class Fake(probe.Credential): pass
        self.reason("CREDENTIAL_TYPE_INVALID", lambda: probe.run_probe(credential=Fake(MARKER)))

    def test_exact_scope_only_eight_apis_and_three_stocks_no_announcement_or_full_market(self):
        for stage in ("SMOKE", "COVERAGE"):
            plan = probe.build_plan(stage)
            self.assertEqual(len(plan), 22)
            self.assertEqual({s.api_name for s in plan}, {"stock_basic", "suspend_d", "trade_cal", "daily", "adj_factor", "dividend", "fina_indicator", "index_member_all"})
            self.assertEqual({dict(s.params)["ts_code"] for s in plan if "ts_code" in dict(s.params)}, set(probe.SYMBOLS))
            self.assertTrue(all(dict(s.params)["ts_type_name"] == probe.BASE_URL for s in plan))
        self.assertEqual(request("dividend", "COVERAGE").max_rows, 256)
        self.assertNotIn("is_new", dict(request("index_member_all").params))

    def test_widened_stock_dates_fields_and_custom_equality_rejected(self):
        original = request()
        for altered in (dataclasses.replace(original, params=(("ts_code", "000001.SZ"),)),
                        dataclasses.replace(original, max_rows=100000), dataclasses.replace(original, api_name="p_delete"),
                        dataclasses.replace(original, start_date="20200101")):
            self.reason("UNAPPROVED_REQUEST_SCOPE", lambda: probe.validate_plan([altered]))
        class Evil(probe.RequestSpec):
            def __eq__(self, other): return True
        evil = Evil(**dataclasses.asdict(original))
        self.reason("UNAPPROVED_REQUEST_SCOPE", lambda: probe.validate_plan([evil]))

    def test_duplicate_mixed_and_excess_budget_rejected(self):
        self.reason("DUPLICATE_REQUEST", lambda: probe.validate_plan([request(), request()]))
        self.reason("MIXED_PLAN_STAGES", lambda: probe.validate_plan([request(), request(stage="COVERAGE")]))
        self.reason("REQUEST_BUDGET_EXCEEDED", lambda: probe.validate_plan([request()] * 23))

    def test_fingerprint_excludes_secret_binds_endpoint_params_fields_and_scope(self):
        self.assertNotEqual(probe.request_fingerprint(request()), probe.request_fingerprint(request(stage="COVERAGE")))
        report = self.synthetic()
        self.assertNotIn(MARKER, json.dumps(report))
        self.assertEqual(report["requests"][0]["request_fingerprint"], probe.request_fingerprint(request()))

    def test_exact_route_sdk_marker_disabled_env_proxy_no_redirect_fallback(self):
        seen = []
        class Response:
            code = 200
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def geturl(self): return probe.BASE_URL + "/daily"
            def read(self, cap): self.cap = cap; return raw(request())
        class Opener:
            def open(self, req, timeout):
                doc = json.loads(req.data)
                seen.append((req.full_url, req.get_method(), doc["params"]["ts_type_name"], timeout))
                return Response()
        with patch.object(probe.urllib.request, "build_opener", return_value=Opener()) as build:
            status, data = probe._live_transport(request(), probe.Credential(MARKER))
        self.assertEqual(seen, [("http://118.89.117.77:8030//daily", "POST", probe.BASE_URL, 20)])
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIs(type(build.call_args.args[1]), probe._NoRedirect)
        self.assertEqual(status, 200)
        self.reason("AUTH_REDIRECT_BLOCKED", lambda: probe._NoRedirect().redirect_request(None))

    def test_transport_exception_echo_does_not_escape_fixed_reason(self):
        class Opener:
            def open(self, *_args, **_kwargs): raise RuntimeError(MARKER)
        with patch.object(probe.urllib.request, "build_opener", return_value=Opener()):
            self.reason("TRANSPORT_ERROR", lambda: probe._live_transport(request(), probe.Credential(MARKER)))

    def test_credential_echo_plain_json_unicode_base64_hex_and_percent_depth0_to12_discard(self):
        credential = probe.Credential(MARKER)
        echo = MARKER
        for depth in range(13):
            self.reason("SECRET_ECHO_DETECTED", lambda: probe._secret_check(json.dumps({"code": -1, "msg": echo}).encode(), credential))
            echo = "".join("%%%02X" % ord(c) for c in echo) if depth == 0 else probe._old.urllib.parse.quote(echo, safe="")
        for encoded in (probe._old.base64.b64encode(MARKER.encode()).decode(), MARKER.encode().hex().upper()):
            self.reason("SECRET_ECHO_DETECTED", lambda: probe._secret_check(json.dumps({"code": -1, "msg": encoded}).encode(), credential))
        unicode = "".join("\\u%04x" % ord(c) for c in MARKER)
        self.reason("SECRET_ECHO_DETECTED", lambda: probe._secret_check(b'{"code":-1,"msg":"' + unicode.encode() + b'"}', credential))

    def test_echo_quarantine_has_no_raw_sha_or_clock_and_no_registration(self):
        before = len(probe._capture_registry)
        report = self.synthetic(data=json.dumps({"code": -1, "msg": MARKER}).encode())
        row = report["requests"][0]
        self.assertEqual(row["reason_codes"], ["SECRET_ECHO_DETECTED"])
        self.assertIsNone(row["raw_sha256"])
        self.assertIsNone(row["retrieved_at"])
        self.assertEqual(len(probe._capture_registry), before)

    def test_empty_success_not_entitlement_or_no_corporate_actions_claim(self):
        item = request("dividend")
        data = raw(item, rows=[])
        analysis = probe.analyze_response(item, data, NOW)
        self.assertEqual(analysis["dq_status"], "EMPTY_NOT_COVERAGE")
        self.assertEqual(analysis["row_count"], 0)
        self.assertEqual(analysis["provider_msg_classification"], "API_SUCCESS_EMPTY_NOT_COVERAGE")

    def test_explicit_denial_auth_rate_and_ambiguity_distinct(self):
        for msg, code, expected in (("当前权限有效但内部异常", -1, "API_ERROR"), ("rate limit prevents permission check", -1, "RATE_LIMITED"),
            ("token无效无法核验权限", -1, "AUTHENTICATION_FAILED"), ("unclassified", 2002, "ENTITLEMENT_NOT_GRANTED")):
            got = probe.analyze_response(request(), json.dumps({"code": code, "msg": msg}).encode(), NOW)
            self.assertEqual(got["provider_msg_classification"], expected)
            self.assertNotIn(msg, json.dumps(got))

    def test_duplicate_invalid_ohlc_negative_volume_and_missing_preclose_block(self):
        item = request()
        doc = json.loads(raw(item))
        doc["data"]["items"].append(doc["data"]["items"][0])
        self.assertEqual(probe.analyze_response(item, json.dumps(doc).encode(), NOW)["dq_reasons"], ["DUPLICATE_KEY"])
        for changes, expected in (({"high": "1"}, "OHLC_INVALID"), ({"vol": "-1"}, "NEGATIVE_VOLUME_AMOUNT"), ({"pre_close": None}, "RAW_BAR_REQUIRED_VALUE_MISSING")):
            self.assertEqual(probe.analyze_response(item, raw(item, **changes), NOW)["dq_reasons"], [expected])

    def test_wrong_symbol_date_unknown_projection_and_nan_block(self):
        item = request()
        self.assertEqual(probe.analyze_response(item, raw(item, ts_code="000001.SZ"), NOW)["dq_reasons"], ["SYMBOL_SCOPE_MISMATCH"])
        self.assertEqual(probe.analyze_response(item, raw(item, trade_date="20261008"), NOW)["dq_reasons"], ["DATE_SCOPE_MISMATCH"])
        doc = json.loads(raw(item)); doc["data"]["fields"].append("adjusted_close"); doc["data"]["items"][0].append("99")
        self.assertEqual(probe.analyze_response(item, json.dumps(doc).encode(), NOW)["dq_reasons"], ["SCHEMA_MISMATCH"])
        self.assertEqual(probe.analyze_response(item, b'{"code":0,"price":NaN}', NOW)["dq_reasons"], ["RESPONSE_JSON_INVALID"])

    def test_decimal_precision_no_rounding_units_and_raw_factor_isolation(self):
        item = request()
        data = raw(item, close="10.30000000000000000001")
        self.assertEqual(probe.analyze_response(item, data, NOW)["dq_status"], "PASS")
        self.assertEqual(dict(item.units)["vol"], "LOT_HAND_NO_SHARE_CONVERSION")
        self.assertEqual(dict(item.units)["amount"], "THOUSAND_YUAN")
        self.assertTrue(item.adjustment.startswith("RAW_UNADJUSTED"))
        self.assertEqual(request("adj_factor").adjustment, "FACTOR_ONLY_NO_ADJUSTED_PRICES")
        self.assertEqual(probe.analyze_response(request("adj_factor"), raw(request("adj_factor"), adj_factor="0"), NOW)["dq_reasons"], ["FACTOR_INVALID"])

    def test_date_only_future_publication_and_invalid_capture_clock_rejected(self):
        item = request("fina_indicator")
        self.assertEqual(probe.analyze_response(item, raw(item, ann_date="20261007"), NOW)["dq_reasons"], ["FUTURE_PUBLICATION_DATE"])
        self.assertEqual(probe.analyze_response(item, raw(item), NOW)["publication_precision"], "DATE_ONLY")
        for value in (MARKER, "2026-10-05", "2026-10-05T18:00:00"):
            self.reason("CLOCK_INVALID", lambda: probe.analyze_response(item, raw(item), value))

    def test_financial_distinct_revision_rows_preserved_not_overwritten(self):
        item = request("fina_indicator")
        doc = json.loads(raw(item)); old = doc["data"]["items"][0]; revised = list(old)
        revised[item.fields.index("update_flag")] = "0"
        revised[item.fields.index("eps")] = "1.234"
        doc["data"]["items"] = [old, revised]
        got = probe.analyze_response(item, json.dumps(doc).encode(), NOW)
        self.assertEqual(got["row_count"], 2)
        self.assertEqual(got["dq_status"], "PASS")
        self.assertFalse(got["revision_history_proven"])
        self.assertEqual(got["coverage"]["unique_report_periods"], 1)

    def test_industry_effective_dates_preserved_no_historical_availability(self):
        item = request("index_member_all")
        got = probe.analyze_response(item, raw(item, is_new="N", out_date="20250301"), NOW)
        self.assertEqual(got["provider_date_fields"]["in_date"], ["20230101"])
        self.assertEqual(got["provider_date_fields"]["out_date"], ["20250301"])
        self.assertFalse(got["industry_historical_visibility_proven"])

    def test_deterministic_saved_raw_replay_and_reordered_rows_normalized_hash(self):
        item = request()
        doc = json.loads(raw(item)); second = list(doc["data"]["items"][0]); second[item.fields.index("trade_date")] = "20260929"
        doc["data"]["items"].append(second)
        first = probe.analyze_response(item, json.dumps(doc).encode(), NOW)
        replay = probe.analyze_response(item, json.dumps(doc).encode(), NOW)
        doc["data"]["items"].reverse()
        reordered = probe.analyze_response(item, json.dumps(doc).encode(), NOW)
        self.assertEqual(first, replay)
        self.assertEqual(first["normalized_hash"], reordered["normalized_hash"])

    def test_api_success_cannot_set_provider_license_historical_or_admission_authority(self):
        report = self.synthetic()
        self.assertFalse(report["provider_identity_verified"])
        self.assertFalse(report["license_verified"])
        self.assertFalse(report["historical_visibility_proven"])
        self.assertFalse(report["productionGate"])
        self.assertTrue(all(value is None for value in report["admission_refs"].values()))
        self.assertTrue(all(value == "BLOCKED" for value in report["gates"].values()))
        self.assertEqual(len(report["categories"]), 8)
        self.assertTrue(all(c["admission_status"] == "BLOCKED" for c in report["categories"]))
        row = report["requests"][0]
        self.assertEqual(row["available_at"], NOW)
        self.assertIsNone(row["published_at"])
        self.assertIsNone(row["event_time"])
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["mock_transport_attempts"], 1)

    def test_caller_cannot_supply_live_transport_clock_endpoint_provider_or_production(self):
        for key in ("clock", "transport", "endpoint", "provider_verified", "productionGate", "retrieved_at"):
            with self.assertRaises(TypeError): probe.run_probe(**{key: True})

    def test_rate_budget_has_no_retry_or_auto_expansion(self):
        items = [request(), request("adj_factor")]
        time = FakeTime(); started = []
        def transport(item, credential): started.append(time.value); return 200, raw(item)
        report = probe.run_synthetic_probe(credential=probe.Credential(MARKER), plan=items, transport=transport, clock=lambda: NOW,
                                          monotonic=time.monotonic, sleeper=time.sleep)
        self.assertEqual(started, [0, 3])
        self.assertEqual(report["mock_transport_attempts"], 2)
        self.reason("LOCAL_RATE_BUDGET_NOT_ENFORCED", lambda: probe.run_synthetic_probe(credential=probe.Credential(MARKER),
            plan=items, transport=transport, clock=lambda: NOW, monotonic=lambda: 0, sleeper=lambda _: None))

    def test_raw_capture_handle_forgery_and_synthetic_real_persistence_blocked(self):
        self.reason("UNREGISTERED_CAPTURE", lambda: probe.persist_capture(probe.CaptureHandle(), "test-run"))
        self.reason("CAPTURE_ISSUER_REQUIRED", lambda: probe._register_capture(raw(request()), request(), probe.Credential(MARKER), 200, NOW, NOW, False))
        self.synthetic()
        entry = list(probe._capture_registry.values())[-1]
        self.reason("SYNTHETIC_CAPTURE_CANNOT_PERSIST_AS_REAL", lambda: probe.persist_capture(entry[0], "test-run"))

    def test_report_mutation_clone_fake_raw_fields_cannot_persist(self):
        report = probe.run_probe(credential=None, run_id="no-secret-report-test")
        self.reason("REPORT_UNREGISTERED", lambda: probe.save_report(dict(report)))
        report["requests"][0]["raw_ref"] = MARKER
        self.reason("REPORT_MUTATED", lambda: probe.save_report(report))

    def test_exclusive_0600_writer_symlinks_traversal_and_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            path = root / "private" / "synthetic.bytes"
            probe._exclusive_write(path, b"synthetic-only")
            self.assertEqual(path.read_bytes(), b"synthetic-only")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.reason("ARTIFACT_EXISTS_NO_OVERWRITE", lambda: probe._exclusive_write(path, b"replace"))
            (root / "link").symlink_to(root / "private", target_is_directory=True)
            self.reason("ARCHIVE_SYMLINK_OR_INVALID_DIRECTORY", lambda: probe._exclusive_write(root / "link" / "bad", b"synthetic"))
            self.reason("RUN_ID_INVALID", lambda: probe._safe_run_id("../traversal"))

    def test_credential_source_metadata_and_persistence_flags_not_forgeable(self):
        class Evil(str):
            def __eq__(self, other): return True
        self.reason("CREDENTIAL_SOURCE_INVALID", lambda: probe.run_probe(credential_source=Evil(MARKER)))
        self.reason("PERSISTENCE_FLAG_INVALID", lambda: probe.run_probe(persist="false"))

    def test_credential_in_run_id_blocked_before_network_or_write(self):
        with patch.object(probe, "_live_transport", side_effect=AssertionError("NO_NETWORK")):
            self.reason("SECRET_ECHO_DETECTED", lambda: probe.run_probe(credential=probe.Credential(MARKER), run_id=MARKER))

    def test_arbitrary_keychain_reference_does_not_trigger_secret_lookup(self):
        def forbidden(*_args, **_kwargs): self.fail("NO_KEYCHAIN_SCAN")
        credential, lookup = probe.lookup_credential(service="unapproved.service", account="other", native_getter=forbidden)
        self.assertIsNone(credential)
        self.assertEqual(lookup["lookup_result"], "UNAPPROVED_KEYCHAIN_REFERENCE")

    def test_invalid_json_unicode_echo_discarded_not_stored_as_error_capture(self):
        escaped = "".join("\\u%04x" % ord(c) for c in MARKER)
        self.reason("SECRET_ECHO_DETECTED", lambda: probe._secret_check(b"invalid-json-" + escaped.encode(), probe.Credential(MARKER)))

    def test_invalid_utf8_encoded_echo_and_nonsecret_discard_before_hash_and_sink(self):
        credential = probe.Credential(MARKER)
        for encoded in (probe._old.base64.b64encode(MARKER.encode()), MARKER.encode().hex().encode(), b"nonsecret"):
            data = b"\xff" + encoded
            self.reason("NON_UTF8_RESPONSE_QUARANTINE", lambda: probe._secret_check(data, credential))
            before = len(probe._capture_registry)
            report = self.synthetic(data=data)
            row = report["requests"][0]
            self.assertEqual(row["reason_codes"], ["NON_UTF8_RESPONSE_QUARANTINE"])
            self.assertEqual(row["status"], "QUARANTINE")
            self.assertIsNone(row["raw_sha256"])
            self.assertIsNone(row["retrieved_at"])
            self.assertIsNone(row["raw_ref"])
            self.assertEqual(len(probe._capture_registry), before)

    def test_security_identity_currency_and_status_are_validated_without_history_claim(self):
        spec = request("stock_basic")
        for changes in ({"symbol": "000001"}, {"exchange": "SZSE"}, {"curr_type": "USD"}):
            analysis = probe.analyze_response(spec, raw(spec, **changes), NOW)
            self.assertEqual(analysis["dq_reasons"], ["SECURITY_IDENTITY_MISMATCH"])
        for status in (None, "ACTIVE", 1):
            analysis = probe.analyze_response(spec, raw(spec, list_status=status), NOW)
            self.assertEqual(analysis["dq_reasons"], ["SECURITY_STATUS_INVALID"])
        for status in ("L", "D", "P"):
            analysis = probe.analyze_response(spec, raw(spec, list_status=status), NOW)
            self.assertEqual(analysis["dq_status"], "PASS")
            self.assertFalse(analysis["revision_history_proven"])

    def test_calendar_pretrade_date_strictly_prior_or_null_never_clock(self):
        spec = request("trade_cal")
        for date in ("20260930", "20261001"):
            analysis = probe.analyze_response(spec, raw(spec, pretrade_date=date), NOW)
            self.assertEqual(analysis["dq_reasons"], ["CALENDAR_PREVIOUS_DATE_INVALID"])
        for date in (None, "20260929"):
            analysis = probe.analyze_response(spec, raw(spec, pretrade_date=date), NOW)
            self.assertEqual(analysis["dq_status"], "PASS")
            self.assertEqual(analysis["publication_precision"], "UNKNOWN")

if __name__ == "__main__": unittest.main()
