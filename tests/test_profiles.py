import stat

from hpk.profiles import (
    apply_templates,
    atomic_write,
    profile_home,
    seed_env_if_absent,
    set_env_key,
)


def test_atomic_write_creates_file_with_mode(tmp_path):
    target = tmp_path / "x.env"
    atomic_write(target, "hello\n", mode=0o600)
    assert target.read_text() == "hello\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_atomic_write_replaces_existing(tmp_path):
    target = tmp_path / "x.env"
    target.write_text("old")
    atomic_write(target, "new", mode=0o600)
    assert target.read_text() == "new"


def test_seed_env_creates_when_missing(tmp_path):
    src = tmp_path / "src.env"
    src.write_text("X=FILL_IN_X\n")
    dst = tmp_path / "p" / ".env"
    seeded = seed_env_if_absent(template=src, target=dst)
    assert seeded is True
    assert dst.read_text() == "X=FILL_IN_X\n"


def test_seed_env_preserves_existing(tmp_path):
    src = tmp_path / "src.env"
    src.write_text("X=FILL_IN_X\n")
    dst = tmp_path / "p" / ".env"
    dst.parent.mkdir()
    dst.write_text("X=secret\n")
    seeded = seed_env_if_absent(template=src, target=dst)
    assert seeded is False
    assert dst.read_text() == "X=secret\n"


def test_set_env_key_replaces_existing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("FOO=FILL_IN\nBAR=keep\n")
    set_env_key(f, "FOO", "real")
    assert "FOO=real" in f.read_text()
    assert "BAR=keep" in f.read_text()


def test_set_env_key_appends_when_missing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("EXISTING=1\n")
    set_env_key(f, "NEW", "v")
    assert "NEW=v" in f.read_text()


def test_apply_templates_copies_soul_and_config(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("soul")
    (template_dir / "config.yaml").write_text("cfg")
    home = tmp_path / "home"
    home.mkdir()
    apply_templates(template_dir=template_dir, profile_home=home, force=False)
    assert (home / "SOUL.md").read_text() == "soul"
    assert (home / "config.yaml").read_text() == "cfg"


def test_apply_templates_skips_existing_without_force(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("new")
    home = tmp_path / "home"
    home.mkdir()
    (home / "SOUL.md").write_text("old")
    apply_templates(template_dir=template_dir, profile_home=home, force=False)
    assert (home / "SOUL.md").read_text() == "old"


def test_apply_templates_overwrites_with_force(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("new")
    home = tmp_path / "home"
    home.mkdir()
    (home / "SOUL.md").write_text("old")
    apply_templates(template_dir=template_dir, profile_home=home, force=True)
    assert (home / "SOUL.md").read_text() == "new"


def test_profile_home_uses_HOME_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert profile_home("coder") == tmp_path / ".hermes" / "profiles" / "coder"
