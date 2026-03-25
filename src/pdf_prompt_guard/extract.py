from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path

import fitz


@dataclass
class PDFExtraction:
    pdf_path: str
    full_text: str
    visible_text: str
    filtered_out_text: str
    method: str


def _rgb_from_int(color: int) -> tuple[int, int, int]:
    return ((color >> 16) & 255, (color >> 8) & 255, color & 255)


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [c / 255.0 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _span_is_visible(span: dict, page_rect: fitz.Rect, min_font_size: float = 4.5) -> bool:
    text = span.get("text", "")
    if not text or not text.strip():
        return False

    bbox_raw = span.get("bbox")
    if not bbox_raw:
        return False

    bbox = fitz.Rect(bbox_raw)
    if not page_rect.intersects(bbox):
        return False

    # render_mode=3 text has alpha=0 (invisible text layer)
    alpha = int(span.get("alpha", 255))
    if alpha < 20:
        return False

    size = float(span.get("size", 0.0))
    if size < min_font_size:
        return False

    color = int(span.get("color", 0))
    if _luminance(_rgb_from_int(color)) > 0.97:
        return False

    return True


def extract_pdf_text_heuristic(pdf_path: str | Path, min_font_size: float = 4.5) -> PDFExtraction:
    doc = fitz.open(str(pdf_path))
    full_pages: list[str] = []
    visible_pages: list[str] = []
    filtered_pages: list[str] = []

    for page in doc:
        visible_spans: list[tuple[float, float, str]] = []
        filtered_out: list[str] = []
        all_spans: list[tuple[float, float, str]] = []

        tree = page.get_text("dict")
        for block in tree.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text or not text.strip():
                        continue

                    y0, x0 = span["bbox"][1], span["bbox"][0]
                    all_spans.append((y0, x0, text))

                    if _span_is_visible(span, page.rect, min_font_size=min_font_size):
                        visible_spans.append((y0, x0, text))
                    else:
                        filtered_out.append(text)

        full_pages.append(" ".join(t for _, _, t in sorted(all_spans)).strip())
        visible_pages.append(" ".join(t for _, _, t in sorted(visible_spans)).strip())
        filtered_pages.append("\n".join(filtered_out).strip())

    doc.close()

    return PDFExtraction(
        pdf_path=str(pdf_path),
        full_text="\n\n".join(p for p in full_pages if p),
        visible_text="\n\n".join(p for p in visible_pages if p),
        filtered_out_text="\n\n".join(p for p in filtered_pages if p),
        method="heuristic_visible_text",
    )


def extract_pdf_text_ocr(pdf_path: str | Path, dpi: int = 200) -> PDFExtraction:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("OCR mode requires: pip install -e .[ocr]") from exc

    doc = fitz.open(str(pdf_path))
    full_pages: list[str] = []
    ocr_pages: list[str] = []

    for page in doc:
        full_pages.append(page.get_text("text", sort=True).strip())

        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_pages.append(pytesseract.image_to_string(image).strip())

    doc.close()

    full_text = "\n\n".join(p for p in full_pages if p)
    visible_text = "\n\n".join(p for p in ocr_pages if p)

    return PDFExtraction(
        pdf_path=str(pdf_path),
        full_text=full_text,
        visible_text=visible_text,
        filtered_out_text="",
        method="ocr_visible_text",
    )


def extract_pdf(pdf_path: str | Path, use_ocr: bool = False) -> PDFExtraction:
    if use_ocr:
        return extract_pdf_text_ocr(pdf_path)
    return extract_pdf_text_heuristic(pdf_path)
