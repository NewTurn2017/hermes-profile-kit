from hpk import ui


def test_ui_emits_without_raising(capsys):
    ui.header("Test")
    ui.step("doing thing")
    ui.ok("done")
    ui.warn("careful")
    ui.err("bad")
    captured = capsys.readouterr()
    assert "Test" in captured.out
    assert "doing thing" in captured.out
    assert "done" in captured.out
    assert "careful" in captured.out  # warn stays on stdout for inline wizard UX
    assert "bad" in captured.err  # err routes to stderr
