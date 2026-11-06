"""Build aligned idle, blink, talk, and smile frames from the mother image."""

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

SOURCE = Path(r"D:\DPH\WhaleGirl_V1_work\00_Reference_FullBody.png")
OUT_DIR = Path(r"D:\DPH\video-call\live2d-models\whale_girl")

LEFT_EYE = (468, 388, 628, 468)
RIGHT_EYE = (628, 392, 736, 468)
MOUTH = (572, 474, 592, 488)
SKIN = (252, 236, 230, 255)
LID = (72, 58, 84, 255)
MOUTH_COLOR = (186, 92, 108, 255)
MOUTH_LINE = (120, 52, 68, 255)
BLUSH = (255, 150, 166, 70)


def _knock_out_white(image: Image.Image) -> Image.Image:
    """Turn the flat white backdrop transparent without eating the costume.

    Args:
        image: Mother image with an opaque near-white background.

    Returns:
        The same drawing with the outer background removed.
    """
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or x < 0 or y < 0 or x >= width or y >= height:
            continue
        red, green, blue, _alpha = pixels[x, y]
        if red < 246 or green < 246 or blue < 246:
            continue
        seen.add((x, y))
        pixels[x, y] = (red, green, blue, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image


def _eye_like(red: int, green: int, blue: int, alpha: int) -> bool:
    """Return whether a pixel belongs to the open eye rather than the hair.

    Args:
        red: Red channel.
        green: Green channel.
        blue: Blue channel.
        alpha: Alpha channel.

    Returns:
        True when the pixel is iris, highlight, or eye white.
    """
    if alpha < 200:
        return False
    if blue > 140 and blue > red + 20 and green > 50:
        return True
    return min(red, green, blue) > 200 and max(red, green, blue) - min(red, green, blue) < 55


def _cover_eyes(image: Image.Image) -> None:
    """Paint closed lids over both eyes, leaving the surrounding hair.

    Args:
        image: Transparent character image modified in place.
    """
    pixels = image.load()
    for box in (LEFT_EYE, RIGHT_EYE):
        left, top, right, bottom = box
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        radius_x = (right - left) / 2
        radius_y = (bottom - top) / 2
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                nx = (x - center_x) / radius_x
                ny = (y - center_y) / radius_y
                if nx * nx + ny * ny > 1:
                    continue
                red, green, blue, alpha = pixels[x, y]
                if _eye_like(red, green, blue, alpha):
                    pixels[x, y] = SKIN
    draw = ImageDraw.Draw(image)
    for box in (LEFT_EYE, RIGHT_EYE):
        left, top, right, bottom = box
        mid_y = (top + bottom) // 2
        draw.arc(
            (left + 6, mid_y - 16, right - 6, mid_y + 18),
            start=200,
            end=340,
            fill=LID,
            width=4,
        )


def _open_mouth(image: Image.Image) -> None:
    """Draw a small open mouth on the existing closed mouth.

    Args:
        image: Transparent character image modified in place.
    """
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = MOUTH
    draw.ellipse((left - 4, top - 2, right + 4, bottom + 8), fill=MOUTH_COLOR)
    draw.arc(
        (left - 4, top - 2, right + 4, bottom + 8),
        start=20,
        end=160,
        fill=MOUTH_LINE,
        width=2,
    )


def _smile(image: Image.Image) -> None:
    """Add a smile and a light blush on top of the open-eyed face.

    Args:
        image: Transparent character image modified in place.
    """
    draw = ImageDraw.Draw(image)
    draw.arc((566, 476, 598, 496), start=20, end=160, fill=MOUTH_LINE, width=3)
    blush = Image.new("RGBA", image.size, (0, 0, 0, 0))
    blush_draw = ImageDraw.Draw(blush)
    blush_draw.ellipse((500, 450, 548, 478), fill=BLUSH)
    blush_draw.ellipse((680, 448, 728, 476), fill=BLUSH)
    image.alpha_composite(blush)


def main() -> None:
    """Write the four aligned frames used by the call page."""
    base = _knock_out_white(Image.open(SOURCE))
    blink = base.copy()
    _cover_eyes(blink)
    talk = base.copy()
    _open_mouth(talk)
    smile = base.copy()
    _smile(smile)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base.save(OUT_DIR / "idle.png")
    blink.save(OUT_DIR / "blink.png")
    talk.save(OUT_DIR / "talk.png")
    smile.save(OUT_DIR / "smile.png")


if __name__ == "__main__":
    main()
