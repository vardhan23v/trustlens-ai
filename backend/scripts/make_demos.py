"""Build the demo assets (content_kit.md D9). `--record` captures real Gemini vision + crew outputs.

    python scripts/make_demos.py            # images
    python scripts/make_demos.py --record   # fixtures app/demo/<id>.<mode>.json (needs GEMINI_API_KEY)
    python scripts/make_demos.py --record viral_post   # only some
"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import piexif  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.config import DEMO_DIR  # noqa: E402

W, H = 1240, 1650
FORWARD_QUALITY, EDIT_QUALITY = 75, 98
LEFT, TOP, BODY, LINE_H = 90, 110, 27, 44

GENUINE = """NORTHBRIDGE INSTITUTE OF TECHNOLOGY
Office of the Controller of Examinations
Ref: NIT/COE/2026/147                                   Date: 22 September 2026

NOTICE - Odd Semester Examination Schedule

All students of 3rd, 5th and 7th semester B.E. are informed that the odd
semester examinations will commence on 10 November 2026. Hall tickets will be
available on the student portal from 3 November 2026.

Examination fee: Rs. 1,800 (regular)      Last date for payment: 20 October 2026
Payment mode: Student portal only. No other payment channel is authorised.

Students with attendance below 75% must contact their Head of Department
before 15 October 2026.

Sd/-
Controller of Examinations""".split("\n")

EDITED_LINES = {
    10: "Examination fee: Rs. 4,800 (regular)      Last date for payment: 5 October 2026",
    11: "Payment mode: UPI to 9876543210@okaxis immediately to avoid late fee of Rs. 500",
}

def font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.truetype("DejaVuSans.ttf", size)


def line_y(i: int) -> int:
    return TOP + i * LINE_H


def render_genuine() -> Image.Image:
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    for i, line in enumerate(GENUINE):
        size = 34 if i == 0 else 30 if i == 4 else BODY
        d.text((LEFT, line_y(i)), line, fill=(20, 20, 20), font=font(size))
    d.line((LEFT, line_y(2) + 40, W - LEFT, line_y(2) + 40), fill=(60, 60, 60), width=2)
    return im


def make_images() -> None:
    genuine_path = DEMO_DIR / "demo_notice_genuine.jpg"
    render_genuine().save(genuine_path, "JPEG", quality=95)

    # Edited copy, the way a forwarded notice is really forged: the genuine JPEG is first re-compressed
    # (a forwarded copy, q75), then two lines are whited-out and re-typed 1 px larger, and the result is
    # exported from an editor at high quality with editor EXIF. The untouched area keeps its q75 history;
    # the re-typed lines do not — that difference is what ELA picks up.
    buf = io.BytesIO()
    Image.open(genuine_path).convert("RGB").save(buf, "JPEG", quality=FORWARD_QUALITY)
    im = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    d = ImageDraw.Draw(im)
    for i, text in EDITED_LINES.items():
        d.rectangle((LEFT - 6, line_y(i) - 4, W - LEFT + 40, line_y(i) + LINE_H - 8), fill="white")
        d.text((LEFT, line_y(i)), text, fill=(20, 20, 20), font=font(BODY + 1))
    exif = piexif.dump({
        "0th": {piexif.ImageIFD.Software: "Adobe Photoshop 25.0", piexif.ImageIFD.DateTime: "2026:09:28 23:41:10"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: "2026:09:22 10:05:00"},
    })
    im.save(DEMO_DIR / "demo_notice_edited.jpg", "JPEG", quality=EDIT_QUALITY, exif=exif)




VIRAL_POST = ["UNESCO has declared \"Jana Gana Mana\"", "the BEST national anthem in the", "world!",
              "", "Proud moment for India.", "Forward to every Indian!"]


def make_viral_post() -> None:
    """A forwarded social post carrying a viral claim (News / Claim demo). Plain render, no edits."""
    im = Image.new("RGB", (1080, 1080), (236, 229, 221))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((70, 150, 1010, 900), radius=28, fill="white", outline=(210, 210, 210), width=2)
    d.text((110, 185), "Forwarded many times", fill=(120, 120, 120), font=font(30))
    for i, line in enumerate(VIRAL_POST):
        d.text((110, 270 + i * 78), line, fill=(20, 20, 20), font=font(52))
    d.text((820, 835), "9:41 am", fill=(140, 140, 140), font=font(28))
    im.save(DEMO_DIR / "demo_viral_post.jpg", "JPEG", quality=90)


def record(only: list[str]) -> None:
    """Record real Gemini output for each demo, exactly as the live pipeline would produce it."""
    from app.config import settings
    from app.routes.demos import DEMOS
    from app.services import gemini_vision
    from app.services.crew import crews

    if not settings.GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY missing in backend/.env")
    for demo in DEMOS:
        if only and demo["id"] not in only:
            continue
        data = (DEMO_DIR / demo["file"]).read_bytes()
        t0 = time.time()
        fx: dict = {"model": settings.GEMINI_MODEL, "recorded_at": time.strftime("%Y-%m-%d %H:%M")}
        if demo["mode"] == "ai_generated":
            fx["visual"] = gemini_vision.assess_synthetic(data, "JPEG").model_dump()
        else:
            n = gemini_vision.extract_news_image(data, "JPEG")
            text = n.claim_in_image.strip() or n.extracted_text[:1500]
            ce, ledger = crews.run_claim_crew(text)
            fx |= {"news_image": n.model_dump(), "claim_evidence": ce.model_dump(), "tool_urls": ledger.items,
                   "tool_errors": ledger.errors}
        out = DEMO_DIR / demo["fixture"]
        out.write_text(json.dumps(fx, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"recorded {out.name} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    make_images()
    make_viral_post()
    print("demo assets written to", DEMO_DIR)
    if "--record" in sys.argv:
        record([a for a in sys.argv[1:] if not a.startswith("--")])
