from hpk.hermes import (
    HermesNotFoundError,  # noqa: F401
    HermesVersionError,  # noqa: F401
    get_version,
    profile_exists,
    run_profile_create,
)


def test_get_version_parses_output(fake_hermes):
    assert get_version() == "0.12.3"
    assert fake_hermes.calls[-1] == ["hermes", "--version"]


def test_profile_exists_true_when_show_succeeds(fake_hermes):
    fake_hermes.add_existing("coder")
    assert profile_exists("coder") is True


def test_profile_exists_false_when_show_fails(fake_hermes):
    assert profile_exists("nope") is False


def test_run_profile_create_records_call(fake_hermes):
    run_profile_create("research")
    assert ["hermes", "profile", "create", "research"] in fake_hermes.calls
