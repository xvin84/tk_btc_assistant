import importlib.util

from conftest import ROOT

spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)


def test_current_version_is_in_both_changelogs():
    # Без раздела в CHANGELOG релиз выйдет с «нет записи в журнале изменений»
    version = release_notes.project_version()
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        section = release_notes.changelog_section(ROOT / name, version)
        assert not section.startswith("_("), f"нет раздела [{version}] в {name}"


def test_version_matches_package():
    from btc_bot import __version__

    assert __version__ == release_notes.project_version()


def test_notes_have_both_languages():
    notes = release_notes.build(release_notes.project_version())
    assert "What's new in v" in notes and "Что нового в v" in notes
