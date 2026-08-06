"""下载 win-capture-audio 源码中 audio-capture-helper.cpp (关键的激活逻辑)."""
import urllib.request
import os

urls = [
    "https://raw.githubusercontent.com/bozbez/win-capture-audio/main/src/audio-capture-helper.cpp",
    "https://raw.githubusercontent.com/bozbez/win-capture-audio/main/src/audio-capture-helper.hpp",
    "https://raw.githubusercontent.com/bozbez/win-capture-audio/main/src/audio-capture.cpp",
    "https://raw.githubusercontent.com/bozbez/win-capture-audio/main/src/common.hpp",
]
out_dir = os.path.join(os.path.dirname(__file__), "win_capture_audio")
os.makedirs(out_dir, exist_ok=True)

for url in urls:
    fname = url.rsplit("/", 1)[-1]
    out_path = os.path.join(out_dir, fname)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"[ok] {fname} ({len(data)} bytes)")
    except Exception as e:
        print(f"[fail] {fname}: {e}")
