import sys
import types

from routes.search import transfer_pan_resource


class FakeQuarkTransfer:
    calls = []

    @classmethod
    def from_alist(cls, alist_url: str, alist_token: str):
        cls.calls.append(("from_alist", alist_url, alist_token))
        return cls()

    def transfer(self, share_url: str, passcode: str):
        self.calls.append(("transfer", share_url, passcode))
        return {"success": True, "task_id": "task-1"}


def test_transfer_pan_resource_is_disabled_without_private_provider_env(monkeypatch):
    monkeypatch.delenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", raising=False)

    result = transfer_pan_resource(
        {
            "share_url": "https://pan.quark.cn/s/abc",
            "pan_type": "quark",
            "password": "1234",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "private_disabled"


def test_transfer_pan_resource_keeps_quark_path_when_private_enabled(monkeypatch):
    fake_module = types.SimpleNamespace(QuarkTransfer=FakeQuarkTransfer)
    FakeQuarkTransfer.calls = []
    monkeypatch.setenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", "true")
    monkeypatch.setitem(sys.modules, "quark_transfer", fake_module)

    result = transfer_pan_resource(
        {
            "share_url": "https://pan.quark.cn/s/abc",
            "pan_type": "quark",
            "password": "1234",
        }
    )

    assert result == {"success": True, "task_id": "task-1"}
    assert FakeQuarkTransfer.calls[-1] == ("transfer", "https://pan.quark.cn/s/abc", "1234")
    assert FakeQuarkTransfer.calls[-2][0] == "from_alist"
