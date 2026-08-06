"""用 requests 直接下载 ApplicationLoopback 示例源码, 绕过 WebFetch 的 markdown 转换."""
import urllib.request

urls = [
    "https://raw.githubusercontent.com/microsoft/Windows-classic-samples/main/Samples/ApplicationLoopback/cpp/LoopbackCapture.cpp",
    "https://raw.githubusercontent.com/microsoft/Windows-classic-samples/main/Samples/ApplicationLoopback/cpp/LoopbackCapture.h",
    "https://raw.githubusercontent.com/microsoft/Windows-classic-samples/main/Samples/ApplicationLoopback/cpp/Common.h",
    "https://raw.githubusercontent.com/microsoft/Windows-classic-samples/main/Samples/ApplicationLoopback/cpp/ApplicationLoopback.cpp",
]

import os
out_dir = os.path.join(os.path.dirname(__file__), "ms_sample")
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
            print(f"[ok] {fname} ({len(data)} bytes) -> {out_path}")
    except Exception as e:
        print(f"[fail] {fname}: {e}")
