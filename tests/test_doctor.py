from types import SimpleNamespace

import cream_agent.doctor as doctor


def test_check_codex_installed_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    result = doctor.check_codex_installed()
    assert result.ok is False
    assert "not found" in result.detail


def test_check_codex_installed_reads_version(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(
        doctor,
        "_run",
        lambda args: SimpleNamespace(returncode=0, stdout="codex 1.2.3\n", stderr=""),
    )
    result = doctor.check_codex_installed()
    assert result.ok is True
    assert "1.2.3" in result.detail


def test_check_mcp_list_failure(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_run",
        lambda args: SimpleNamespace(returncode=1, stdout="", stderr="permission denied"),
    )
    result, output = doctor.check_mcp_list()
    assert result.ok is False
    assert output == "permission denied"


def test_check_robinhood_trading_configured_found():
    result = doctor.check_robinhood_trading_configured("robinhood-trading connected")
    assert result.ok is True


def test_check_robinhood_trading_configured_missing():
    result = doctor.check_robinhood_trading_configured("market-data connected")
    assert result.ok is False
    assert "codex mcp add robinhood-trading" in result.detail
