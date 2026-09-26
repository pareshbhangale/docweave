"""
CLI for docweave (AI-Supervised PDF-to-Markdown).
"""

import sys
import argparse
from pathlib import Path

from docweave.converter import convert


def main():
    parser = argparse.ArgumentParser(
        prog="docweave",
        description="Convert PDFs to Markdown with TypeSafe System One (Jev) ambiguity routing and table QA auditing."
    )
    parser.add_argument("input_pdf", type=Path, help="Path to input PDF file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output markdown file path")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Docling thread count (default: 10)")
    parser.add_argument("-b", "--batch-size", type=int, default=16, help="Docling batch size (default: 16)")
    parser.add_argument("--no-qa", action="store_true", help="Disable table QA audit")

    args = parser.parse_args()

    if not args.input_pdf.exists():
        print(f"Error: Input PDF '{args.input_pdf}' does not exist.", file=sys.stderr)
        sys.exit(1)

    output_file = args.output
    if output_file is None:
        output_file = args.input_pdf.with_suffix(".md")

    print(f"🚀 Converting '{args.input_pdf.name}' with docweave (TypeSafe Jev supervision)...")
    res = convert(
        args.input_pdf,
        output_path=output_file,
        num_threads=args.threads,
        table_batch_size=args.batch_size,
        audit_quality=not args.no_qa
    )

    print(f"✅ Conversion complete!")
    print(f"  - Pages: {res['total_pages']} (Fast Text: {res['fast_text_pages']}, Docling Tables: {res['docling_pages']})")
    print(f"  - Ambiguous pages routed by Jev: {res['ambiguous_routed_by_jev']}")
    print(f"  - Tables audited: {res['table_qa_audited']}")
    print(f"  - Time: {res['elapsed_sec']}s ({res['sec_per_page']}s/page)")
    print(f"  - Output: {output_file}")


if __name__ == "__main__":
    main()
