"""Citation-check subcommand (``pdf-toolkit check-citations``)."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_check_citations(args: argparse.Namespace) -> int:
    """Flag DOCX text similar to a PDF source, for citation review."""
    import json

    from ..citations import CitationError, compare_documents

    try:
        results = compare_documents(
            args.docx,
            args.pdf,
            threshold=args.threshold,
            min_chunk_length=args.min_chunk_length,
            context_sentences=args.context_sentences,
            max_window=args.max_window_size,
            min_pdf_snippet_length=args.min_pdf_snippet_length,
            min_overlap=args.min_overlap,
            skip_cited=args.skip_cited,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except (CitationError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2
    except ImportError as exc:
        print(f"Error: {exc}")
        return 1

    if args.json_out:
        payload = [match.to_dict() for match in results]
        with Path(args.json_out).open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"Wrote JSON report to {args.json_out}")
    else:
        if not results:
            print("No matches found.")
        for match in results:
            print("---")
            print(f"Doc chunk id: {match.doc_chunk_id} ({match.doc_source})")
            print(f"Similarity: {match.score}")
            print(f"PDF page: {match.page_number}")
            if match.has_citation_marker:
                print("Note: doc chunk carries a citation marker; review it anyway.")
            print("PDF snippet:")
            print(match.pdf_snippet)
            if match.pdf_context:
                print("PDF context:")
                print(match.pdf_context)
            print("Doc text:")
            print(match.doc_text)

    print(f"Found {len(results)} matches (threshold {args.threshold})")
    return 1 if results else 0
