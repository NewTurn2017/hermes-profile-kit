from hpk import ui


def test_ui_emits_without_raising(capsys):
    ui.header("Test")
    ui.step("doing thing")
    ui.ok("done")
    ui.warn("careful")
    ui.err("bad")
    out = capsys.readouterr().out
    assert "Test" in out and "doing thing" in out and "done" in out
