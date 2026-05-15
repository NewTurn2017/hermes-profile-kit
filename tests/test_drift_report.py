from scripts.drift_report import compute_diff, render_markdown


def test_compute_diff_added_removed_renamed():
    old = [{"path": "a", "params": []}, {"path": "b", "params": []}]
    new = [{"path": "a", "params": []}, {"path": "c", "params": []}]
    added, removed = compute_diff(old, new)
    assert added == ["c"] and removed == ["b"]


def test_render_markdown():
    md = render_markdown(added=["c"], removed=["b"], old_sha="old", new_sha="new")
    assert "c" in md and "b" in md and "new" in md
