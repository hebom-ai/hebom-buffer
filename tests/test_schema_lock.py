# -*- coding: utf-8 -*-
"""⛔ v1 immutability lock. Failing here means someone changed a promise."""
import inspect
from hebom import SCHEMA_ID, SCHEMA_VERSION, MODES, result
from hebom.schema import CLASSES, CLASS_NAMES, ORIGIN_LOCAL, ORIGIN_HEBOM
import hebom.telemetry as T

def test_schema_pinned():
    assert SCHEMA_ID.endswith("/buffer-result/1") and SCHEMA_VERSION.startswith("1.")

def test_modes_frozen():
    assert len(MODES) == 12
    assert MODES["E01"] == "loss" and MODES["E12"] == "false_completion"

def test_every_mode_has_a_class():
    assert set(CLASSES) == set(MODES)
    assert set(CLASSES.values()) <= set(CLASS_NAMES)

def test_result_shape():
    r = result("E07", False, "x")
    assert r["mode"] == "schema_mismatch" and r["class"] == "SCHEMA"
    assert r["origin"] == ORIGIN_LOCAL

def test_local_run_cannot_claim_hebom_verified():
    try:
        result("E07", False, origin=ORIGIN_HEBOM)
        assert False, "a local run must not be able to claim hebom_verified"
    except ValueError: pass

def test_telemetry_off_by_default(monkeypatch=None):
    import importlib, os
    os.environ.pop("HEBOM_TELEMETRY", None)
    importlib.reload(T)
    assert T.ENABLED_DEFAULT is False
    assert T.Telemetry().enabled is False

def test_install_id_not_derived_from_machine():
    src = inspect.getsource(T._install_id)
    for banned in ("platform.node", "gethostname", "getuser", "uuid.getnode", "MAC"):
        assert banned not in src, f"install id must not use {banned}"

def test_telemetry_never_sends_identity():
    t = T.Telemetry(enabled=False); t.note("E01", False)
    p = t.payload()
    assert set(p) == {"schema","v","origin","install","package","python",
                      "blocked","by_class","passed"}
    blob = __import__("json").dumps(p)
    for leak in (__import__("platform").node(), __import__("os").getcwd()):
        if leak: assert leak not in blob
