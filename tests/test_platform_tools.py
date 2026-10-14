import io
import sys
import zipfile

from btc_bot import platform_tools as pt


def test_configured_adb_path_wins(tmp_path):
    adb = tmp_path / "adb.exe"
    adb.write_bytes(b"")
    assert pt.find_adb(str(adb)) == str(adb)
    assert pt.find_adb(str(tmp_path / "missing" / "adb")) is None


def test_downloaded_adb_is_found_when_not_in_path(tmp_path, monkeypatch):
    monkeypatch.setattr(pt.shutil, "which", lambda name: None)
    monkeypatch.setattr(pt, "PLATFORM_TOOLS_DIR", tmp_path / "platform-tools")
    assert pt.find_adb() is None
    (tmp_path / "platform-tools").mkdir()
    (tmp_path / "platform-tools" / pt.adb_name()).write_bytes(b"")
    assert pt.find_adb() == str(tmp_path / "platform-tools" / pt.adb_name())


def test_download_unpacks_archive(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"platform-tools/{pt.adb_name()}", b"adb")
        zf.writestr("platform-tools/NOTICE.txt", b"")
    data = buf.getvalue()

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(data))}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    urls = []
    monkeypatch.setattr(pt.urllib.request, "urlopen",
                        lambda url, timeout: urls.append(url) or Response(data))
    monkeypatch.setattr(pt, "PLATFORM_TOOLS_DIR", tmp_path / "platform-tools")
    progress = []
    adb = pt.download_platform_tools(lambda got, total: progress.append((got, total)))

    assert adb == str(tmp_path / "platform-tools" / pt.adb_name())
    assert (tmp_path / "platform-tools" / pt.adb_name()).read_bytes() == b"adb"
    assert progress[-1] == (len(data), len(data))
    assert urls[0].endswith(f"platform-tools-latest-{pt.download_os()}.zip")
    assert sys.platform == "win32" or (tmp_path / "platform-tools" / "adb").stat().st_mode & 0o111
