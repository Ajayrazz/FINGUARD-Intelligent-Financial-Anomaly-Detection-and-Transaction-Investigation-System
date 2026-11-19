"""Image loading, preprocessing and Tesseract OCR. OCR is really executed; if Tesseract is missing this raises."""

from __future__ import annotations

import io
from collections import defaultdict

from PIL import Image, ImageOps

MAX_PIXELS = 40_000_000  # decompression-bomb guard
MAX_PDF_PAGES = 5
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class OcrUnavailable(Exception):
    """The Tesseract binary is not installed or not runnable."""


def load_pages(data: bytes, mime: str) -> list[Image.Image]:
    """PNG/JPEG -> one page; PDF -> up to MAX_PDF_PAGES rendered pages (pypdfium2, no external poppler)."""
    if mime == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        return [pdf[i].render(scale=2.0).to_pil().convert("RGB") for i in range(min(len(pdf), MAX_PDF_PAGES))]
    img = Image.open(io.BytesIO(data))
    img.load()
    return [img.convert("RGB")]


def preprocess(img: Image.Image) -> Image.Image:
    """Grayscale, stretch contrast, and upscale small scans (Tesseract is happiest around 300 dpi)."""
    g = ImageOps.autocontrast(ImageOps.grayscale(img))
    if g.width < 1400:
        scale = 1400 / g.width
        g = g.resize((round(g.width * scale), round(g.height * scale)), Image.Resampling.LANCZOS)
    return g


def ocr_lines(img: Image.Image) -> list[tuple[str, float]]:
    """[(line text, mean word confidence 0-100)] in reading order."""
    import pytesseract

    try:
        data = pytesseract.image_to_data(preprocess(img), output_type=pytesseract.Output.DICT, config="--psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailable("Tesseract is not installed") from exc
    lines: dict[tuple[int, int, int], list[tuple[str, float]]] = defaultdict(list)
    for text, conf, b, p, ln in zip(
        data["text"], data["conf"], data["block_num"], data["par_num"], data["line_num"], strict=True
    ):
        if text.strip() and float(conf) >= 0:
            lines[(b, p, ln)].append((text, float(conf)))
    return [(" ".join(w for w, _ in ws), sum(c for _, c in ws) / len(ws)) for _, ws in sorted(lines.items())]


def phash(img: Image.Image) -> int:
    """64-bit perceptual hash as an int (robust to rescaling, compression and slight rotation/noise)."""
    import imagehash

    return int(str(imagehash.phash(img.convert("L"))), 16)
