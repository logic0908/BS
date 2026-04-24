from __future__ import annotations

import os
import urllib.parse
import subprocess


def _download(url: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    subprocess.run(
        ["curl", "-L", "--fail", "--retry", "5", "--retry-all-errors", "-o", tmp, url],
        check=True,
    )
    os.replace(tmp, dst)


def main() -> None:
    base = "https://huggingface.co/datasets/GTSinger/GTSinger/resolve/main/"
    ref_path = "Chinese/ZH-Tenor-1/Breathy/不染/Breathy_Group/0000.wav"
    src_path = "Chinese/ZH-Alto-1/Mixed_Voice_and_Falsetto/青花瓷/Control_Group/0000.wav"

    out_dir = "/home/featurize/work/BS/backend/data/demo"
    ref_dst = os.path.join(out_dir, "gtsinger_ref.wav")
    src_dst = os.path.join(out_dir, "gtsinger_src.wav")

    ref_url = base + urllib.parse.quote(ref_path)
    src_url = base + urllib.parse.quote(src_path)

    _download(ref_url, ref_dst)
    _download(src_url, src_dst)

    print(ref_dst)
    print(src_dst)


if __name__ == "__main__":
    main()
