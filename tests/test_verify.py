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
