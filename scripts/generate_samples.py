#!/usr/bin/env python3
"""Pre-generate short EN/ID voice samples into data/samples/ for instant UI playback."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.core.audio_utils import encode_audio, save_audio_file
from app.core.manager import get_manager
from app.engines.base import BaseTTSEngine


def main() -> None:
    mgr = get_manager()
    samples_dir = Path(__file__).resolve().parent.parent / "web" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    target_engines = sys.argv[1:] if len(sys.argv) > 1 else ["kokoro", "edge"]

    for eng_name in target_engines:
        try:
            eng = mgr.get(eng_name)
        except KeyError:
            print(f"[skip] Unknown engine: {eng_name}")
            continue

        if not isinstance(eng, BaseTTSEngine) or not eng.is_available():
            print(f"[skip] {eng_name} not installed")
            continue

        print(f"=== Generating short samples for {eng.display_name} ===")
        for v in eng.list_voices():
            safe_eng = "".join(c for c in eng.name if c.isalnum() or c in ("-", "_"))
            safe_voice = "".join(c for c in v.id if c.isalnum() or c in ("-", "_"))
            dest = samples_dir / f"{safe_eng}_{safe_voice}.mp3"
            if dest.exists():
                print(f"  [cached] {dest.name}")
                continue

            is_id = v.language.lower().startswith("id") or v.id.startswith(("id_", "id-"))
            text = "Halo, ini contoh suara saya." if is_id else "Hello, this is a voice sample."
            lang_arg = "id" if is_id else ("en-gb" if v.id.startswith("b") else "en-us")

            try:
                res = eng.synthesize(text=text, voice=v.id, language=lang_arg, speed=1.0)
                audio_bytes, actual_fmt, dur = encode_audio(res.samples, res.sample_rate, "mp3")
                out_path = samples_dir / f"{safe_eng}_{safe_voice}.{actual_fmt}"
                save_audio_file(audio_bytes, out_path)
                print(f"  [ok] {out_path.name} ({dur:.1f}s)")
            except Exception as exc:
                print(f"  [err] {v.id}: {exc}")

        eng.unload()


if __name__ == "__main__":
    main()
