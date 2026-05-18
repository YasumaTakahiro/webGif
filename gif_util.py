from pathlib import Path

from PIL import Image, ImageSequence


def ensure_gif_loops(path: Path) -> bool:
    """アニメ GIF を無限ループ (loop=0) で書き直す。静止画はそのまま。"""
    path = Path(path)
    try:
        with Image.open(path) as im:
            try:
                frame_count = im.n_frames
            except AttributeError:
                return False
            if frame_count <= 1:
                return False

            frames = [frame.copy() for frame in ImageSequence.Iterator(im)]
            if len(frames) <= 1:
                return False

            durations = [f.info.get("duration") or 100 for f in frames]
            disposal = im.info.get("disposal", 2)

            frames[0].save(
                path,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                disposal=disposal,
                optimize=False,
            )
        return True
    except Exception:
        return False


def fix_all_upload_gifs(upload_dir: Path) -> int:
    fixed = 0
    for path in sorted(upload_dir.glob("*.gif")):
        if ensure_gif_loops(path):
            fixed += 1
    return fixed
