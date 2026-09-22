import json
import os

import pytest

import cita_auto


@pytest.fixture()
def fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(cita_auto, "STATE_DIR", str(tmp_path))
    monkeypatch.setattr(cita_auto, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(cita_auto, "TOKENS_PATH", str(tmp_path / "tokens.json"))
    return tmp_path / "state.json"


def test_parse_slots_empty():
    assert cita_auto.parse_slots({}) == []
    assert cita_auto.parse_slots(None) == []
    assert cita_auto.parse_slots({"Slots": []}) == []


def test_parse_slots_sorted_earliest_first():
    resp = {
        "Slots": [
            {"date": "2026-08-20", "times": {"15:00": {}, "09:00": {}}},
            {"date": "2026-08-19", "times": {"10:00": {}}},
        ]
    }
    slots = cita_auto.parse_slots(resp)
    assert slots == [
        {"date": "2026-08-19", "time": "10:00", "meta": {}},
        {"date": "2026-08-20", "time": "09:00", "meta": {}},
        {"date": "2026-08-20", "time": "15:00", "meta": {}},
    ]
    dates = [s["date"] + s["time"] for s in slots]
    assert dates == sorted(dates), "slots must be earliest-first"


def test_parse_slots_drops_widget_error_bodies():
    resp = {"Slots": [{"date": None, "times": {}}]}
    assert cita_auto.parse_slots(resp) == []


def test_parse_slots_lowercase_and_list_times():
    resp = {
        "slots": [
            {"date": "2026-10-15", "times": ["11:00", "09:30"]},
            {"date": "2026-10-14", "times": ["14:00"]}
        ]
    }
    slots = cita_auto.parse_slots(resp)
    assert len(slots) == 3
    assert slots[0] == {"date": "2026-10-14", "time": "14:00", "meta": {}}
    assert slots[1] == {"date": "2026-10-15", "time": "09:30", "meta": {}}
    assert slots[2] == {"date": "2026-10-15", "time": "11:00", "meta": {}}


def test_parse_slots_flat_and_datetime_formats():
    resp1 = [{"date": "2026-11-01", "time": "08:30"}]
    assert cita_auto.parse_slots(resp1) == [{"date": "2026-11-01", "time": "08:30", "meta": {}}]

    resp2 = {"availableSlots": [{"date": "2026-11-05 10:15:00"}]}
    assert cita_auto.parse_slots(resp2) == [{"date": "2026-11-05", "time": "10:15", "meta": {"date": "2026-11-05 10:15:00"}}]


def test_assign_slots_one_per_user_earliest():
    pending = [{"login": "u1"}, {"login": "u2"}, {"login": "u3"}]
    slots = [
        {"date": "2026-08-19", "time": "10:00"},
        {"date": "2026-08-20", "time": "09:00"},
    ]
    pairs = cita_auto.assign_slots(pending, slots)
    assert pairs == [
        (pending[0], slots[0]),
        (pending[1], slots[1]),
    ], "earliest slot must go to first pending user, one distinct slot each"


def test_assign_slots_more_slots_than_users():
    pending = [{"login": "u1"}]
    slots = [
        {"date": "2026-08-19", "time": "10:00"},
        {"date": "2026-08-20", "time": "09:00"},
    ]
    pairs = cita_auto.assign_slots(pending, slots)
    assert len(pairs) == 1
    assert pairs[0][1] == slots[0]


def test_assign_slots_no_slots():
    assert cita_auto.assign_slots([{"login": "u1"}], []) == []


def test_note_booked_persists(fresh_state):
    assert cita_auto.load_state() == {}
    cita_auto.note_booked("C001")
    st = json.loads(fresh_state.read_text())
    assert st["booked_logins"] == ["C001"]
    assert "C001" in st["last_booked"]
    cita_auto.note_booked("C001")
    st = json.loads(fresh_state.read_text())
    assert st["booked_logins"] == ["C001"], "must not duplicate logins"


def test_self_accounts_no_selector_returns_all():
    conf = {"accounts": [{"login": "C001"}, {"login": "C002"}]}
    assert len(cita_auto.self_accounts(conf, None)) == 2


def test_self_accounts_selector_exact_and_partial():
    conf = {"accounts": [{"login": "C00462638"}, {"login": "C00319853"}]}
    assert [a["login"] for a in cita_auto.self_accounts(conf, "C00462638")] == ["C00462638"]
    assert [a["login"] for a in cita_auto.self_accounts(conf, "62638")] == ["C00462638"]
    assert cita_auto.self_accounts(conf, "NOPE") == []


def test_watch_without_auto_book_stays_read_only_and_exits(fresh_state, monkeypatch):
    conf = {
        "auto_book": False,
        "poll_interval": 1,
        "accounts": [{"login": "u1"}, {"login": "u2"}],
    }
    slot = [_slot(19, "10:00")]
    monkeypatch.setattr(cita_auto, "load_session", lambda: {"captured": 0})
    monkeypatch.setattr(
        cita_auto, "api_check_auto",
        lambda conf, session, verbose=True, drv=None: (list(slot), "ok", None))
    monkeypatch.setattr(cita_auto.time, "sleep", lambda _s: None)
    rc = cita_auto.watch_mode(conf, None)
    assert rc == 0
    st = cita_auto.load_state()
    assert st.get("booked_logins") is None, "read-only watch must never mark users booked"


def test_self_accounts_legacy_credentials():
    conf = {"credentials": {"login": "C001"}}
    assert cita_auto.self_accounts(conf, None) == [{"login": "C001"}]
    assert cita_auto.self_accounts({}, None) == []


def _slot(day, time):
    return {"date": f"2026-08-{day:02d}", "time": time, "meta": {}}


def _run_watch(conf, poll_results, fresh_state, monkeypatch, book_ok=True):
    calls = []
    queue = list(poll_results)

    class StopPoll(Exception):
        pass

    def fake_browser_api_check(drv, conf, verbose=True):
        if not queue:
            raise StopPoll()
        return (queue.pop(0), "ok")

    def fake_start_browser_lane(conf):
        return "DRV"

    def fake_book_one_in_driver(drv, conf, acc, slot, logfn):
        calls.append((acc, slot))
        return book_ok

    def fake_quit_driver(drv):
        pass

    monkeypatch.setattr(cita_auto, "load_session", lambda: {"captured": 0})
    monkeypatch.setattr(cita_auto, "start_browser_lane", fake_start_browser_lane)
    monkeypatch.setattr(cita_auto, "browser_api_check", fake_browser_api_check)
    monkeypatch.setattr(cita_auto, "book_one_in_driver", fake_book_one_in_driver)
    monkeypatch.setattr(cita_auto, "quit_driver", fake_quit_driver)
    monkeypatch.setattr(cita_auto.time, "sleep", lambda _s: None)
    try:
        rc = cita_auto.watch_mode(conf, None)
        return rc, calls
    except StopPoll:
        return None, calls


def test_watch_auto_book_books_all_in_two_waves(fresh_state, monkeypatch):
    conf = {
        "auto_book": True,
        "poll_interval": 1,
        "accounts": [
            {"login": "u1"}, {"login": "u2"}, {"login": "u3"}, {"login": "u4"},
        ],
    }
    wave1 = [_slot(19, "10:00"), _slot(19, "12:00")]
    wave2 = [_slot(21, "09:00"), _slot(21, "11:00")]
    rc, calls = _run_watch(conf, [wave1, wave2], fresh_state, monkeypatch)

    assert rc == 0
    assert len(calls) == 4
    assert set(a["login"] for a, s in calls[:2]) == {"u1", "u2"}
    assert set(s["time"] for a, s in calls[:2]) == {"10:00", "12:00"}
    assert set(a["login"] for a, s in calls[2:]) == {"u3", "u4"}
    assert set(s["time"] for a, s in calls[2:]) == {"09:00", "11:00"}
    assert set(json.loads(fresh_state.read_text())["booked_logins"]) == {"u1", "u2", "u3", "u4"}


def test_watch_auto_book_respects_existing_booked(fresh_state, monkeypatch):
    conf = {
        "auto_book": True,
        "poll_interval": 1,
        "accounts": [
            {"login": "u1"}, {"login": "u2"}, {"login": "u3"},
        ],
    }
    cita_auto.note_booked("u1")
    slot = [_slot(19, "10:00")]
    rc, calls = _run_watch(conf, [slot, slot], fresh_state, monkeypatch)

    assert rc == 0
    logged_in = [a["login"] for a, s in calls]
    assert logged_in == ["u2", "u3"]
    assert calls[0][1]["time"] == "10:00"


def test_watch_auto_book_slot_failure_keeps_user_pending(fresh_state, monkeypatch):
    conf = {
        "auto_book": True,
        "poll_interval": 1,
        "accounts": [{"login": "u1"}, {"login": "u2"}],
    }
    wave1 = [_slot(19, "10:00")]
    wave2 = [_slot(19, "10:00")]
    rc, calls = _run_watch(conf, [wave1, wave2], fresh_state, monkeypatch, book_ok=False)

    assert rc is None, "loop must not exit while users remain unbooked"
    assert len(calls) == 2
    logged_in = [a["login"] for a, s in calls]
    assert logged_in == ["u1", "u1"], "failed user must be retried, not re-assigned another"


def test_tokens_auto_save_and_expire(fresh_state):
    # Save valid token
    entry = cita_auto.save_account_token("C001", {"token": "tok_123", "ttl": 3600})
    assert entry["token"] == "tok_123"
    assert cita_auto.get_account_token("C001")["token"] == "tok_123"

    # Overwrite with new token
    entry2 = cita_auto.save_account_token("C001", {"token": "tok_456", "ttl": 3600})
    assert entry2["token"] == "tok_456"
    assert cita_auto.get_account_token("C001")["token"] == "tok_456"

    # Expired token auto-removed
    cita_auto.save_account_token("C002", {"token": "tok_exp", "ttl": -10})
    assert cita_auto.get_account_token("C002") is None
    assert "C002" not in cita_auto.load_tokens()


def test_save_booking_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(cita_auto, "RECEIPTS_DIR", str(tmp_path))
    get_calls = []
    cdp_calls = []
    class FakeDriver:
        def get(self, url):
            get_calls.append(url)
        def execute_cdp_cmd(self, cmd, args):
            cdp_calls.append((cmd, args))
            import base64
            return {"data": base64.b64encode(b"%PDF-1.4 real consular receipt").decode("ascii")}
    acc = {"login": "TEST_C001"}
    slot = {"date": "2026-09-22", "time": "09:15"}
    pdf_path = cita_auto.save_booking_pdf(FakeDriver(), {}, acc, slot)
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert open(pdf_path, "rb").read() == b"%PDF-1.4 real consular receipt"
    # Ensure no synthetic template or data URL navigation was performed
    assert get_calls == [], "Must not navigate away from the live Bookitit page"
    assert len(cdp_calls) == 1
    assert cdp_calls[0][0] == "Page.printToPDF"
    assert cdp_calls[0][1].get("printBackground") is True


def test_deep_check_account_already_booked(tmp_path, monkeypatch):
    monkeypatch.setattr(cita_auto, "RECEIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(cita_auto, "do_login", lambda d, c, a, l: None)
    monkeypatch.setattr(cita_auto, "note_booked", lambda l: None)
    class FakeElement:
        text = "Martes 22 de Septiembre de 2026 - 09:15h · TRÁMITES DE VISADOS"
    class FakeDriver:
        current_url = "https://www.citaconsular.es/es/hosteds/widgetdefault/hash/#history"
        def get(self, url): pass
        def execute_script(self, script, *args): pass
        def find_element(self, by, val): return FakeElement()
        def execute_cdp_cmd(self, cmd, args):
            import base64
            return {"data": base64.b64encode(b"%PDF-1.4 real booked").decode("ascii")}

    conf = {"widget_url": "https://www.citaconsular.es/es/hosteds/widgetdefault/hash/"}
    acc = {"login": "TEST_C001", "password": "pw"}
    res = cita_auto.deep_check_account(FakeDriver(), conf, acc)
    assert res["status"] == "already_booked"
    assert res["pdf"] is not None
    assert os.path.exists(res["pdf"])


def test_deep_check_account_no_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(cita_auto, "RECEIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(cita_auto, "do_login", lambda d, c, a, l: None)
    monkeypatch.setattr(cita_auto, "select_service", lambda d, c, l: None)
    monkeypatch.setattr(cita_auto, "accept_terms", lambda d, c, l: None)
    monkeypatch.setattr(cita_auto, "select_agenda", lambda d, l: None)
    monkeypatch.setattr(cita_auto, "browser_api_check", lambda d, c, verbose=False: ([], "no slots"))
    class FakeElement:
        text = "NO TIENES NINGUNA CITA | Volver a pedir cita"
    class FakeDriver:
        current_url = "https://www.citaconsular.es/es/hosteds/widgetdefault/hash/#datetime"
        def get(self, url): pass
        def execute_script(self, script, *args):
            if "selectDay" in script: return []
            if "nextBtn" in script: return False
            return None
        def find_element(self, by, val): return FakeElement()

    conf = {"widget_url": "https://www.citaconsular.es/es/hosteds/widgetdefault/hash/", "date_start": "2026-09-16", "date_end": "2027-12-31"}
    acc = {"login": "TEST_C002", "password": "pw"}
    res = cita_auto.deep_check_account(FakeDriver(), conf, acc)
    assert res["status"] == "no_slots"
    assert res["slots"] == []


def test_api_direct_book_in_page_success(monkeypatch):
    class FakeDriver:
        def execute_async_script(self, script, *args):
            return {"ok": True, "endpoint": "signedin", "resp": {"id": 12345}}

    conf = {"office_hash": "testhash", "widget_url": "https://example.com/widget/"}
    acc = {"login": "C001", "password": "pw", "profile": {"first_name": "John"}}
    slot = {"date": "2026-09-25", "time": "11:30"}
    ok, res = cita_auto.api_direct_book_in_page(FakeDriver(), conf, acc, slot, "dummy_token")
    assert ok is True
    assert res.get("endpoint") == "signedin"


def test_api_direct_book_external_success(monkeypatch):
    monkeypatch.setattr(cita_auto, "load_session", lambda: {"cookies": [{"name": "cf_clearance", "value": "xyz"}]})

    class FakeApiClient:
        def __init__(self, conf, session): pass
        def _post(self, ep, payload):
            if ep == "signedin/":
                return {"id": 999, "status": "ok"}
            return {"_error": "not found"}

    monkeypatch.setattr(cita_auto, "ApiClient", FakeApiClient)
    conf = {"office_hash": "testhash", "widget_url": "https://example.com/widget/"}
    acc = {"login": "C001", "password": "pw"}
    slot = {"date": "2026-09-25", "time": "11:30"}
    ok, res = cita_auto.api_direct_book_external(conf, acc, slot, "dummy_token")
    assert ok is True
    assert res.get("id") == 999


def test_book_slot_anyhow_falls_back_to_token_api_when_browser_crashes(fresh_state, monkeypatch):
    # Save a cached token for user
    cita_auto.save_account_token("C0099", {"token": "live_jwt_token", "ttl": 3600})

    # Direct external API mock returns success
    monkeypatch.setattr(cita_auto, "api_direct_book_external", lambda conf, acc, slot, tok, logfn: (True, {"id": 888}))
    monkeypatch.setattr(cita_auto, "export_pdf_for_account", lambda conf, acc, slot, logfn: None)

    conf = {"office_hash": "testhash", "widget_url": "https://example.com/widget/"}
    acc = {"login": "C0099", "password": "pw"}
    slot = {"date": "2026-09-25", "time": "11:30"}

    # Simulate browser completely crashed / drv is None
    ok = cita_auto.book_slot_anyhow(conf, acc, slot, drv=None)
    assert ok is True
    assert "C0099" in cita_auto.load_state()["booked_logins"]


def test_telegram_notifications(monkeypatch, tmp_path):
    monkeypatch.setattr(cita_auto, "STATE_DIR", str(tmp_path))
    monkeypatch.setattr(cita_auto, "TELEGRAM_CHATS_PATH", str(tmp_path / "telegram_chats.json"))

    sent_messages = []

    def fake_notify(conf, text, parse_mode="HTML", document_path=None):
        sent_messages.append({"text": text, "doc": document_path})
        return True

    monkeypatch.setattr(cita_auto, "telegram_notify", fake_notify)

    conf = {
        "office_name": "Consulado de España",
        "telegram": {"enabled": True, "bot_token": "fake_token", "chat_id": "12345"}
    }

    # Test slot found notification
    slots = [{"date": "2026-10-01", "time": "09:30"}, {"date": "2026-10-01", "time": "10:00"}]
    res = cita_auto.telegram_notify_slot_found(conf, slots, "2026-10-01..2026-10-31")
    assert res is True
    assert len(sent_messages) == 1
    assert "FREE APPOINTMENT SLOTS AVAILABLE" in sent_messages[0]["text"]
    assert "2026-10-01" in sent_messages[0]["text"]
    assert "09:30" in sent_messages[0]["text"]

    # Test booking success notification
    acc = {
        "login": "TEST_USER_99",
        "password": "SecretPassword123",
        "profile": {"first_name": "Carlos", "last_name": "Santana"}
    }
    slot = {"date": "2026-10-01", "time": "09:30"}
    res_book = cita_auto.telegram_notify_booking_success(conf, acc, slot, pdf_path=None)
    assert res_book is True
    assert len(sent_messages) == 2
    book_msg = sent_messages[1]["text"]
    assert "APPOINTMENT SUCCESSFULLY BOOKED" in book_msg
    assert "Carlos Santana" in book_msg
    assert "TEST_USER_99" in book_msg
    assert "SecretPassword123" in book_msg
    assert "2026-10-01 at 09:30h" in book_msg

    # Test live check notification
    res_live = cita_auto.telegram_notify_live_check(conf, round_no=1, interval=5, window="all", pending_count=3, total_count=4, force=True)
    assert res_live is True
    assert len(sent_messages) == 3
    assert "CITA AUTO: 24/7 Real-Time Live Status" in sent_messages[2]["text"]