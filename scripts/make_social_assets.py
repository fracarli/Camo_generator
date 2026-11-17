"""Create LinkedIn images, a PDF carousel and a short video for the web game.

Run after `terrainweave game build`:

    python scripts/make_social_assets.py --site output/game-site --output output/linkedin

Requires ffmpeg on PATH for the video. Text is in Italian by default.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

URL = "https://fracarli.github.io/Camo_generator/"
SHORT_URL = "fracarli.github.io/Camo_generator"
SIZE = (1080, 1350)
PINE = (31, 42, 28)
CREAM = (243, 241, 232)
MOSS = (155, 172, 112)
LIME = (213, 226, 173)
GOLD = (255, 212, 59)
ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ("s03-forest", "s07-jungle", "s00-desert")
COMPARE = "s05-forest"
FONT_FILE = Path("/System/Library/Fonts/Avenir Next.ttc")
FACES = {"heavy": 8, "bold": 0, "medium": 5, "regular": 7}


def font(face: str, size: int) -> ImageFont.FreeTypeFont:
    if FONT_FILE.is_file():
        return ImageFont.truetype(str(FONT_FILE), size, index=FACES[face])
    return ImageFont.load_default(size)


class Site:
    def __init__(self, root: Path):
        self.root = root
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.scenes = {scene["id"]: scene for scene in manifest["scenes"]}

    def image(self, scene_id: str, variant: str = "optimized") -> Image.Image:
        with Image.open(self.root / "scenes" / scene_id / f"{variant}.jpg") as image:
            return image.convert("RGB")

    def box(self, scene_id: str, size: tuple[int, int]) -> tuple[float, float, float, float]:
        x, y, w, h = self.scenes[scene_id]["box"]
        return x * size[0], y * size[1], w * size[0], h * size[1]


def rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius, fill=255)
    result = Image.new("RGBA", image.size)
    result.paste(image, (0, 0), mask)
    return result


def ring(draw: ImageDraw.ImageDraw, box, width: int = 7) -> None:
    x, y, w, h = box
    pad_x, pad_y = w * 0.55, h * 0.14
    shape = (x - pad_x, y - pad_y, x + w + pad_x, y + h + pad_y)
    draw.ellipse(shape, outline=(0, 0, 0), width=width + 6)
    draw.ellipse(shape, outline=GOLD, width=width)


def text_block(draw, xy, text, face, size, fill=CREAM, width=980, spacing=1.12):
    """Draw wrapped text and return the y coordinate below it."""
    typeface = font(face, size)
    x, y = xy
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=typeface) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    for line in lines:
        draw.text((x, y), line, font=typeface, fill=fill)
        y += round(size * spacing)
    return y


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, PINE)
    draw = ImageDraw.Draw(image)
    # Camouflage-like brand stripe in the corner.
    draw.polygon([(SIZE[0] - 150, 0), (SIZE[0], 0), (SIZE[0], 150)], fill=(69, 89, 61))
    draw.polygon([(SIZE[0] - 90, 0), (SIZE[0] - 60, 0), (SIZE[0], 60), (SIZE[0], 90)], fill=MOSS)
    draw.text((50, 48), "TERRAINWEAVE", font=font("bold", 30), fill=MOSS)
    return image, draw


def footer(draw, page: int | None = None, total: int = 6) -> None:
    draw.text((50, SIZE[1] - 72), SHORT_URL, font=font("medium", 28), fill=LIME)
    if page:
        label = f"{page}/{total}"
        length = draw.textlength(label, font=font("bold", 28))
        draw.text((SIZE[0] - 50 - length, SIZE[1] - 72), label, font=font("bold", 28), fill=MOSS)


def paste_scene(base: Image.Image, scene: Image.Image, top: int, width: int = 980) -> tuple:
    scale = width / scene.width
    resized = scene.resize((width, round(scene.height * scale)), Image.Resampling.LANCZOS)
    left = (SIZE[0] - width) // 2
    base.paste(rounded(resized, 26), (left, top), rounded(resized, 26))
    return left, top, scale


def qr_image(size: int) -> Image.Image:
    import qrcode

    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    code.add_data(URL)
    code.make(fit=True)
    image = code.make_image(fill_color="#1f2a1c", back_color="#f3f1e8").convert("RGB")
    return image.resize((size, size), Image.Resampling.NEAREST)


def crop_around(site: Site, scene_id: str, variant: str, aspect: float, zoom: float) -> tuple:
    """Crop a window around the figure; return the crop and the figure box inside it."""
    image = site.image(scene_id, variant)
    x, y, w, h = site.box(scene_id, image.size)
    height = min(image.height, h * zoom)
    width = min(image.width, height * aspect)
    height = width / aspect
    cx, cy = x + w / 2, y + h / 2
    left = min(max(0, cx - width / 2), image.width - width)
    top = min(max(0, cy - height / 2), image.height - height)
    crop = image.crop((round(left), round(top), round(left + width), round(top + height)))
    return crop, (x - left, y - top, w, h)


# --- Carousel ---------------------------------------------------------------


def challenge_slide(site, scene_id, page, title, subtitle):
    image, draw = canvas()
    y = text_block(draw, (50, 130), title, "heavy", 76)
    text_block(draw, (50, y + 10), subtitle, "medium", 36, fill=LIME)
    paste_scene(image, site.image(scene_id), 430)
    draw.text((50, 1130), "Scorri per la soluzione  »", font=font("bold", 34), fill=CREAM)
    footer(draw, page)
    return image


def solutions_slide(site, page):
    image, draw = canvas()
    text_block(draw, (50, 130), "Eccoli.", "heavy", 84)
    top = 270
    for scene_id in CHALLENGE:
        crop, box = crop_around(site, scene_id, "optimized", 3.6, 2.0)
        scale = 980 / crop.width
        crop = crop.resize((980, round(crop.height * scale)), Image.Resampling.LANCZOS)
        ring(ImageDraw.Draw(crop), [value * scale for value in box], width=6)
        image.paste(rounded(crop, 22), (50, top), rounded(crop, 22))
        top += crop.height + 22
    text_block(
        draw,
        (50, top + 10),
        "Ogni omino indossa un mimetismo generato da TerrainWeave.",
        "medium",
        34,
        fill=LIME,
    )
    footer(draw, page)
    return image


def compare_slide(site, page):
    image, draw = canvas()
    y = text_block(draw, (50, 130), "Stessa foto, stesso punto.", "heavy", 70)
    y = text_block(draw, (50, y + 6), "Cambia solo il mimetismo.", "heavy", 70, fill=LIME)
    top = y + 40
    for variant, label in (("control", "Verde oliva tinta unita"), ("optimized", "TerrainWeave")):
        crop, box = crop_around(site, COMPARE, variant, 0.8, 1.7)
        crop = crop.resize((475, round(475 / crop.width * crop.height)), Image.Resampling.LANCZOS)
        left = 50 if variant == "control" else 555
        image.paste(rounded(crop, 22), (left, top), rounded(crop, 22))
        draw.text((left, top + crop.height + 16), label, font=font("bold", 32), fill=CREAM)
        bottom = top + crop.height + 70
    text_block(
        draw,
        (50, bottom + 20),
        "TerrainWeave analizza foto reali di boschi, deserti, montagne e città e genera "
        "mimetismi su misura. Ora vogliamo sapere quale funziona davvero sull'occhio umano.",
        "regular",
        34,
        fill=LIME,
        spacing=1.35,
    )
    footer(draw, page)
    return image


def call_slide(page):
    image, draw = canvas()
    y = text_block(draw, (50, 130), "Mettiti alla prova.", "heavy", 84)
    y = text_block(draw, (50, y), "4 giochi da 1 minuto.", "heavy", 84, fill=LIME)
    y += 30
    for name, text in (
        ("Caccia", "trova l'omino il più in fretta possibile"),
        ("Duello", "due mimetismi a confronto: quale scovi prima?"),
        ("Lampo", "un quarto di secondo: c'era o no?"),
        ("Pattuglia", "4 omini nella stessa foto: trovali tutti"),
    ):
        draw.text((50, y), name, font=font("heavy", 42), fill=CREAM)
        y = text_block(draw, (290, y + 6), text, "medium", 34, fill=LIME, width=740) + 18
    qr = qr_image(420)
    image.paste(qr, ((SIZE[0] - 420) // 2, y + 40))
    caption = "Inquadra o apri il link"
    length = draw.textlength(caption, font=font("bold", 34))
    draw.text(((SIZE[0] - length) / 2, y + 480), caption, font=font("bold", 34), fill=CREAM)
    text_block(
        draw,
        (50, SIZE[1] - 150),
        "Anonimo, senza registrazione. Ogni partita aiuta a migliorare i mimetismi.",
        "regular",
        28,
        fill=MOSS,
    )
    footer(draw, page)
    return image


def single_post(site):
    image, draw = canvas()
    y = text_block(draw, (50, 120), "Trovi l'omino mimetizzato?", "heavy", 78)
    paste_scene(image, site.image(CHALLENGE[0]), y + 30)
    qr = qr_image(250)
    image.paste(qr, (50, 1020))
    text_block(
        draw,
        (330, 1030),
        "Gioca in 1 minuto e aiutaci a capire quali mimetismi funzionano davvero.",
        "bold",
        36,
        width=700,
    )
    footer(draw)
    return image


# --- Video ------------------------------------------------------------------


def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, t)))


def video_frames(site, fps: int = 30):
    title, _ = canvas()
    draw = ImageDraw.Draw(title)
    y = text_block(draw, (50, 420), "C'è un omino nascosto.", "heavy", 92)
    text_block(draw, (50, y + 20), "Hai 4 secondi per trovarlo.", "heavy", 64, fill=LIME)
    for frame in range(int(fps * 2.2)):
        yield title

    for number, scene_id in enumerate(CHALLENGE, 1):
        scene = site.image(scene_id)
        box = site.box(scene_id, scene.size)
        base, draw = canvas()
        text_block(draw, (50, 130), f"Foto {number} di 3", "heavy", 64)
        left, top, scale = paste_scene(base, scene, 360)
        bar_top = top + round(scene.height * scale) + 40
        seconds = 4.0
        for frame in range(int(fps * seconds)):
            image = base.copy()
            d = ImageDraw.Draw(image)
            left_time = 1 - frame / (fps * seconds)
            d.rounded_rectangle((50, bar_top, 1030, bar_top + 18), 9, fill=(60, 75, 55))
            color = (217, 72, 15) if left_time < 0.25 else MOSS
            d.rounded_rectangle((50, bar_top, 50 + 980 * left_time, bar_top + 18), 9, fill=color)
            count = str(math.ceil(left_time * seconds))
            d.text((50, bar_top + 50), count, font=font("heavy", 110), fill=CREAM)
            yield image
        # Reveal: zoom into the figure and draw the ring.
        reveal = int(fps * 2.0)
        x, y, w, h = box
        cx, cy = x + w / 2, y + h / 2
        for frame in range(reveal):
            t = ease(frame / (reveal * 0.6))
            zoom = 1 + 1.4 * t
            width, height = scene.width / zoom, scene.height / zoom
            crop_left = min(max(0, cx - width / 2), scene.width - width)
            crop_top = min(max(0, cy - height / 2), scene.height - height)
            view = scene.crop((crop_left, crop_top, crop_left + width, crop_top + height))
            view = view.resize(
                (980, round(980 * scene.height / scene.width)), Image.Resampling.LANCZOS
            )
            factor = 980 / width
            if frame > reveal * 0.35:
                ring(
                    ImageDraw.Draw(view),
                    ((x - crop_left) * factor, (y - crop_top) * factor, w * factor, h * factor),
                    width=8,
                )
            image = base.copy()
            image.paste(rounded(view, 26), (left, top), rounded(view, 26))
            d = ImageDraw.Draw(image)
            d.rectangle((40, bar_top - 10, 1040, bar_top + 200), fill=PINE)
            d.text((50, bar_top + 30), "Eccolo!", font=font("heavy", 90), fill=GOLD)
            yield image

    final = call_slide(None)
    for frame in range(int(fps * 4.5)):
        yield final


def write_video(site, destination: Path, fps: int = 30) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{SIZE[0]}x{SIZE[1]}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "20",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    for frame in video_frames(site, fps):
        process.stdin.write(frame.convert("RGB").tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise SystemExit("ffmpeg failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "output/game-site")
    parser.add_argument("--output", type=Path, default=ROOT / "output/linkedin")
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()
    site = Site(args.site)
    args.output.mkdir(parents=True, exist_ok=True)
    slides = [
        challenge_slide(
            site,
            CHALLENGE[0],
            1,
            "C'è un omino nascosto in questa foto.",
            "Riesci a trovarlo in 5 secondi?",
        ),
        challenge_slide(
            site, CHALLENGE[1], 2, "E in questa giungla?", "Stesso omino, mimetismo diverso."
        ),
        challenge_slide(
            site,
            CHALLENGE[2],
            3,
            "L'ultima è la più difficile.",
            "Chi lo trova al primo colpo lo scriva nei commenti.",
        ),
        solutions_slide(site, 4),
        compare_slide(site, 5),
        call_slide(6),
    ]
    for number, slide in enumerate(slides, 1):
        slide.save(args.output / f"carousel_{number}.png")
    slides[0].save(
        args.output / "carousel.pdf", save_all=True, append_images=slides[1:], resolution=150
    )
    single_post(site).save(args.output / "post_single.png")
    qr_image(1000).save(args.output / "qr_code.png")
    if not args.no_video:
        if shutil.which("ffmpeg") is None:
            raise SystemExit("ffmpeg is required for the video (use --no-video to skip)")
        write_video(site, args.output / "video_trova_omino.mp4")
    print(f"Assets written to {args.output}")


if __name__ == "__main__":
    main()
