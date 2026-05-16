from subprocess import CompletedProcess

from hpk.verify import VerifyResult, fill_in_findings, run_verify


def test_fill_in_findings(tmp_path):
    f = tmp_path / "a.env"
    f.write_text("A=ok\nB=FILL_IN_B\nC=keep\nD=FILL_IN_D\n")
    rows = list(fill_in_findings(f))
    assert rows == [(2, "B"), (4, "D")]


def test_run_verify_aggregates(fake_hermes, tmp_path, monkeypatch):
    fake_hermes.add_existing("coder")
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=ok\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    r = run_verify(["coder"])
    assert isinstance(r, VerifyResult)
    assert r.passing == ["coder"] and r.fill_in_remaining == {}


def test_run_verify_failing_doctor(fake_hermes, tmp_path, monkeypatch):
    """Doctor returning non-zero lands the profile in `failing` with the stderr reason."""
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=ok\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk import hermes as _h

    def failing_doctor(name: str | None = None) -> CompletedProcess[str]:
        return CompletedProcess(["hermes", "doctor"], 1, stdout="", stderr="boom\n")

    monkeypatch.setattr(_h, "run_doctor", failing_doctor)

    r = run_verify(["coder"])
    assert r.passing == []
    assert r.failing == [("coder", "boom")]
    assert r.ok is False


def test_run_verify_fill_in_remaining_only(fake_hermes, tmp_path, monkeypatch):
    """FILL_IN placeholders surface even when doctor is green; result.ok is False."""
    fake_hermes.add_existing("coder")
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    r = run_verify(["coder"])
    assert r.passing == ["coder"]  # doctor green
    assert r.fill_in_remaining == {"coder": [(1, "ANTHROPIC_API_KEY")]}
    assert r.ok is False
