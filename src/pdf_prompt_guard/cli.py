from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from pdf_prompt_guard.report import analyze_pdf_to_report, write_report


def make_dummy_resume(out_path: str) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Taylor Lee")
    y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Lubbock, TX | taylor.lee@example.com | github.com/taylorlee")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Summary")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Software engineer with experience in Python, Java, SQL, Git, Linux, and backend services.")
    y -= 28

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Experience")
    y -= 16
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Software Engineer - Example Labs")
    y -= 14
    c.setFont("Helvetica", 10)
    lines = [
        "- Built internal tools in Python and Java.",
        "- Wrote SQL queries and maintained Linux-based services.",
        "- Collaborated with Git-based development workflows.",
    ]
    for line in lines:
        c.drawString(60, y, line)
        y -= 14

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Skills")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Python, Java, SQL, Git, Linux")

    c.save()


def add_visible_redteam_note(input_pdf: str, output_pdf: str, text: str) -> None:
    in_path = Path(input_pdf)
    out_path = Path(output_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(in_path))
    page = doc[0]

    rect = fitz.Rect(36, page.rect.height - 140, page.rect.width - 36, page.rect.height - 36)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=(0.75, 0.2, 0.2), fill=(1.0, 0.94, 0.94), width=1.2)
    shape.commit()

    note = "RED TEAM TEST NOTE - VISIBLE\n" + text
    page.insert_textbox(
        fitz.Rect(rect.x0 + 8, rect.y0 + 8, rect.x1 - 8, rect.y1 - 8),
        note,
        fontsize=10,
        fontname="helv",
        color=(0.35, 0.0, 0.0),
        align=0,
    )

    doc.save(str(out_path))
    doc.close()


def _build_ats_stuffing(job_path: str) -> str:
    """Read the job description and return it as-is for hidden injection.

    Using the raw text preserves word order so that both single-word and
    bigram keywords extracted during scoring will match exactly.
    """
    return Path(job_path).read_text(encoding="utf-8")


def inject_hidden_prompt(input_pdf: str, output_pdf: str, text: str, method: str = "invisible") -> None:
    """Insert instruction text that is invisible to humans but present in the embedded text layer."""
    in_path = Path(input_pdf)
    out_path = Path(output_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(in_path))

    if method == "invisible":
        fontsize = 1
        color = (0, 0, 0)
        render_mode = 3   # PDF invisible text — zero visual pixels, fully extractable
        overlay = False    # place behind existing content
    elif method == "tiny":
        fontsize = 1
        color = (0, 0, 0)
        render_mode = 0
        overlay = True
    elif method == "white":
        fontsize = 4
        color = (1, 1, 1)
        render_mode = 0
        overlay = True
    else:
        raise ValueError(f"Unknown method '{method}'. Choose 'invisible', 'tiny', or 'white'.")

    remaining = text
    for page in doc:
        if not remaining:
            break

        rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)

        rc = page.insert_textbox(rect, remaining, fontsize=fontsize, fontname="helv",
                                 color=color, align=0, render_mode=render_mode,
                                 overlay=overlay)
        if rc >= 0:
            remaining = ""
        else:
            fitted = len(remaining) - abs(int(rc))
            remaining = remaining[fitted:]

    doc.save(str(out_path))
    doc.close()

    injected = len(text) - len(remaining)
    print(f"Injected hidden text ({method}) into: {out_path}")
    print(f"Hidden text: {len(text)} chars total, {injected} chars injected")
    if remaining:
        print(f"WARNING: {len(remaining)} chars did not fit")


def analyze_pdf(pdf_path: str, job_path: str, out_path: str, use_ocr: bool) -> None:
    job_text = Path(job_path).read_text(encoding="utf-8")
    report = analyze_pdf_to_report(pdf_path=pdf_path, job_text=job_text, use_ocr=use_ocr)
    write_report(report, out_path)

    print(json.dumps({
        "pdf": str(pdf_path),
        "method": report["extraction_method"],
        "vulnerable_score": report["vulnerable_score"],
        "hardened_score": report["hardened_score"],
        "suspicious_hidden_like_content": report["suspicious_hidden_like_content"],
        "out": str(out_path),
    }, indent=2))


def batch_analyze(pdf_dir: str, job_path: str, out_dir: str, use_ocr: bool) -> None:
    pdf_root = Path(pdf_dir)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    job_text = Path(job_path).read_text(encoding="utf-8")

    pdf_files = sorted(pdf_root.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {pdf_root}")

    summary: list[dict[str, object]] = []
    for pdf_path in pdf_files:
        report = analyze_pdf_to_report(pdf_path=pdf_path, job_text=job_text, use_ocr=use_ocr)
        out_path = out_root / f"{pdf_path.stem}.json"
        write_report(report, out_path)
        summary.append(
            {
                "pdf": pdf_path.name,
                "method": report["extraction_method"],
                "vulnerable_score": report["vulnerable_score"],
                "hardened_score": report["hardened_score"],
                "vulnerable_recommend_interview": report["vulnerable_recommend_interview"],
                "hardened_recommend_interview": report["hardened_recommend_interview"],
                "suspicious_hidden_like_content": report["suspicious_hidden_like_content"],
            }
        )

    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"processed": len(summary), "summary": str(summary_path)}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-prompt-guard")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("make-dummy-resume", help="Create a dummy resume PDF")
    p1.add_argument("--out", required=True)

    p2 = sub.add_parser("add-visible-redteam-note", help="Add a clearly visible red-team note to a PDF")
    p2.add_argument("--input", required=True)
    p2.add_argument("--output", required=True)
    p2.add_argument("--text", required=True)

    p2h = sub.add_parser("inject-hidden-prompt", help="Inject invisible prompt text into a PDF (for detection research)")
    p2h.add_argument("--input", required=True)
    p2h.add_argument("--output", required=True)
    p2h.add_argument("--text", default=None, help="Manual prompt injection text")
    p2h.add_argument("--job", default=None, help="Path to job description — auto-extracts keywords for ATS stuffing")
    p2h.add_argument("--method", choices=["invisible", "tiny", "white"], default="invisible",
                     help="invisible=render_mode 3 (default, zero pixels); tiny=1pt font; white=white text")

    p3 = sub.add_parser("analyze", help="Analyze one PDF")
    p3.add_argument("--pdf", required=True)
    p3.add_argument("--job", required=True)
    p3.add_argument("--out", required=True)
    p3.add_argument("--ocr", action="store_true")

    p4 = sub.add_parser("batch-analyze", help="Analyze all PDFs in a folder")
    p4.add_argument("--pdf-dir", required=True)
    p4.add_argument("--job", required=True)
    p4.add_argument("--out-dir", required=True)
    p4.add_argument("--ocr", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "make-dummy-resume":
        make_dummy_resume(args.out)
    elif args.command == "add-visible-redteam-note":
        add_visible_redteam_note(args.input, args.output, args.text)
    elif args.command == "inject-hidden-prompt":
        parts: list[str] = []
        if args.job:
            ats_text = _build_ats_stuffing(args.job)
            parts.append(ats_text)
            print(f"Auto-generated ATS keywords from job description ({len(ats_text)} chars)")
        if args.text:
            parts.append(args.text)
        if not parts:
            parser.error("inject-hidden-prompt requires at least --text or --job")
        hidden_text = "\n\n".join(parts)
        inject_hidden_prompt(args.input, args.output, hidden_text, method=args.method)
    elif args.command == "analyze":
        analyze_pdf(args.pdf, args.job, args.out, use_ocr=args.ocr)
    elif args.command == "batch-analyze":
        batch_analyze(args.pdf_dir, args.job, args.out_dir, use_ocr=args.ocr)


if __name__ == "__main__":
    main()
