"""
docweave: AI-Supervised PDF-to-Markdown with TypeSafe (Jev) System One
======================================================================
Focuses on semantic ambiguity resolution and table extraction quality auditing:
1. Batched Ambiguity Routing: Disambiguates borderline border boxes, schedules, and letterheads in 1 HTTP call.
2. In-Flight Quality Audit: Evaluates financial table conversions with Jev Noul & Score primitives.
"""

import io
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import pymupdf
import pymupdf4llm

from .client import TypeSafePDFClient, get_typesafe_credentials

_JEV_CLIENT = None
_DOCLING_CONVERTER = None


def get_jev_client() -> Optional[TypeSafePDFClient]:
    global _JEV_CLIENT
    if _JEV_CLIENT is None:
        try:
            creds = get_typesafe_credentials()
            if creds.get("api_key") or "127.0.0.1" in creds.get("endpoint", "") or "localhost" in creds.get("endpoint", ""):
                _JEV_CLIENT = TypeSafePDFClient()
        except Exception:
            _JEV_CLIENT = None
    return _JEV_CLIENT


def get_docling_converter(num_threads: int = 10, table_batch_size: int = 16):
    global _DOCLING_CONVERTER
    if _DOCLING_CONVERTER is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        pipeline_options.table_batch_size = table_batch_size
        pipeline_options.layout_batch_size = table_batch_size
        pipeline_options.accelerator_options = AcceleratorOptions(device="auto", num_threads=num_threads)

        _DOCLING_CONVERTER = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
    return _DOCLING_CONVERTER


def inspect_page_geometry(page: pymupdf.Page):
    words = page.get_text("words")
    chars = sum(len(w[4]) for w in words)
    images = len(page.get_images(full=True))
    drawings_list = page.get_drawings()
    drawings = len(drawings_list)
    page_h = page.rect.height

    h_lines = 0
    v_lines = 0
    body_lines = 0
    for d in drawings_list:
        rect = d.get("rect")
        if rect:
            w, h = rect.width, rect.height
            if w > 30 and h < 3.5:
                h_lines += 1
                if rect.y1 > page_h * 0.32:
                    body_lines += 1
            elif h > 20 and w < 3.5:
                v_lines += 1
                if rect.y1 > page_h * 0.32:
                    body_lines += 1

    return chars, images, drawings, h_lines, v_lines, body_lines


def convert(
    pdf_path: Path,
    output_path: Optional[Path] = None,
    num_threads: int = 10,
    table_batch_size: int = 16,
    audit_quality: bool = True
) -> Dict[str, Any]:
    """
    Converts a PDF using Jev-supervised hybrid conversion.
    """
    start = time.perf_counter()
    doc = pymupdf.open(str(pdf_path))
    num_pages = len(doc)

    t0_class = time.perf_counter()
    classes = [""] * num_pages
    ambiguous_candidates = []

    # Fast geometry pass (<0.5ms)
    for i, page in enumerate(doc):
        chars, images, drawings, h_lines, v_lines, body_lines = inspect_page_geometry(page)
        if chars < 100 and images > 0:
            classes[i] = "OCR"
        elif (body_lines >= 4 and v_lines >= 2) or (body_lines >= 8):
            classes[i] = "TABLE"
        elif body_lines == 0 and drawings < 30 and h_lines < 3:
            classes[i] = "TEXT_SIMPLE"
        else:
            ambiguous_candidates.append({
                "page_idx": i,
                "char_count": chars,
                "drawings": drawings,
                "images": images,
                "tables": 1 if (body_lines >= 2 or h_lines >= 4) else 0,
                "text_sample": page.get_text()[:600]
            })

    # Ambiguity resolution via TypeSafe System One (Jev)
    client = get_jev_client()
    if ambiguous_candidates:
        if client:
            try:
                resolved = client.route_ambiguous_batch(ambiguous_candidates)
                for idx, r_class in resolved.items():
                    classes[idx] = r_class
            except Exception:
                pass
        for cand in ambiguous_candidates:
            if not classes[cand["page_idx"]]:
                classes[cand["page_idx"]] = "TABLE" if cand["tables"] > 0 else "TEXT_SIMPLE"

    class_time = time.perf_counter() - t0_class

    docling_pages_0idx = [i for i, c in enumerate(classes) if c in ("TABLE", "COMPLEX", "OCR")]
    pymupdf_pages_0idx = [i for i, c in enumerate(classes) if c not in ("TABLE", "COMPLEX", "OCR")]

    page_markdown = [""] * num_pages

    table_ratio = len(docling_pages_0idx) / max(num_pages, 1)
    if num_pages >= 20 and table_ratio > 0.60:
        converter = get_docling_converter(num_threads=num_threads, table_batch_size=table_batch_size)
        res = converter.convert(str(pdf_path))
        PAGE_DELIM = "\n\n\n---\n\n\n"
        final_md = res.document.export_to_markdown(page_break_placeholder=PAGE_DELIM)
    else:
        if pymupdf_pages_0idx:
            text_chunks = pymupdf4llm.to_markdown(doc, pages=pymupdf_pages_0idx, page_chunks=True, use_ocr=False)
            for item in text_chunks:
                page_markdown[item["metadata"]["page_number"] - 1] = item["text"].strip()

        if docling_pages_0idx:
            from docling.datamodel.base_models import DocumentStream

            converter = get_docling_converter(num_threads=num_threads, table_batch_size=table_batch_size)
            sub_doc = pymupdf.open()
            for idx in docling_pages_0idx:
                sub_doc.insert_pdf(doc, from_page=idx, to_page=idx)
            pdf_bytes = sub_doc.tobytes()
            sub_doc.close()

            stream = DocumentStream(name=pdf_path.name, stream=io.BytesIO(pdf_bytes))
            res = converter.convert(stream)
            PAGE_DELIM = "\n\n<!-- PAGE_SPLIT -->\n\n"
            full_sub_md = res.document.export_to_markdown(page_break_placeholder=PAGE_DELIM)
            parts = full_sub_md.split(PAGE_DELIM)
            if len(parts) == len(docling_pages_0idx):
                for o_idx, p_md in zip(docling_pages_0idx, parts):
                    page_markdown[o_idx] = p_md.strip()
            else:
                for s_idx, o_idx in enumerate(docling_pages_0idx, start=1):
                    page_markdown[o_idx] = res.document.export_to_markdown(page_no=s_idx).strip()

        final_md = "\n\n\n---\n\n\n".join([p for p in page_markdown if p.strip()])

    doc.close()

    # Step 3: Targeted Table QA Audit (Only audit pages containing actual table syntax)
    qa_results = []
    if audit_quality and docling_pages_0idx and not (num_pages >= 20 and table_ratio > 0.60):
        if client:
            table_pages_to_audit = [
                {"page_num": idx + 1, "markdown": page_markdown[idx]}
                for idx in docling_pages_0idx
                if page_markdown[idx].strip() and ("|" in page_markdown[idx] and "---" in page_markdown[idx])
            ]
            if table_pages_to_audit:
                try:
                    qa_results = client.audit_tables_batch(table_pages_to_audit[:10])
                except Exception:
                    pass

    elapsed = time.perf_counter() - start

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(final_md, encoding="utf-8")

    return {
        "engine": "docweave-jev",
        "doc": pdf_path.name,
        "total_pages": num_pages,
        "classification_time": round(class_time, 3),
        "ambiguous_routed_by_jev": len(ambiguous_candidates),
        "fast_text_pages": len(pymupdf_pages_0idx),
        "docling_pages": len(docling_pages_0idx),
        "elapsed_sec": round(elapsed, 2),
        "sec_per_page": round(elapsed / num_pages, 3),
        "output_chars": len(final_md),
        "table_qa_audited": len(qa_results),
        "qa_results": qa_results
    }
