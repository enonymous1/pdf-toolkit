import re

import fitz

try:
    # Configure tesseract path
    import os as _os

    import pytesseract
    from pytesseract import Output

    if _os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = _os.environ["TESSERACT_CMD"]
except ImportError:
    pytesseract = None
    Output = None

try:
    import cv2
except ImportError:
    cv2 = None


def clean_ocr_token(text: str) -> str:
    """Cleans up individual OCR tokens, especially those misread from leader dots."""
    if not text:
        return ""

    # Whitelist tokens with numbers (likely section or page numbers)
    if any(char.isdigit() for char in text):
        return text

    # Remove junk characters often misread from leader dots (e.g. 'ceces')
    # but keep short words like 'and', 'the', 'of', 'for', 'in'.
    if re.fullmatch(r"[cesxo\.]{4,}", text, re.I):
        return ""

    return text


def get_ocr_text_robust(page: fitz.Page, dpi: int = 400) -> str:
    """
    Enhanced OCR extraction using high DPI, noise removal, and coordinate-aware reconstruction.
    """
    if not pytesseract:
        return page.get_text("text") or ""

    try:
        import numpy as np
        from PIL import Image

        # 1. High DPI Rendering for small text fidelity
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w)

        # 2. Preprocessing
        if cv2:
            # Adaptive binarization to handle varying lighting/scans
            binary = cv2.adaptiveThreshold(
                img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
            )

            # Remove small noise and thin leader dots using connected components
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                binary, connectivity=8
            )
            cleaned = np.zeros_like(binary)
            for i in range(1, num_labels):
                w = stats[i, cv2.CC_STAT_WIDTH]
                h = stats[i, cv2.CC_STAT_HEIGHT]
                area = stats[i, cv2.CC_STAT_AREA]

                # Keep components that are likely characters
                # At 400 DPI, a typical 10pt character is ~50-100 pixels area
                if area > 12 and (w > 4 or h > 4):
                    cleaned[labels == i] = 255

            # Invert back to standard black-on-white for Tesseract
            img = 255 - cleaned

        # 3. OCR with Word-Level Data
        pil_img = Image.fromarray(img)
        # PSM 6 is generally best for uniform text blocks like TOC
        data = pytesseract.image_to_data(pil_img, config="--psm 6", output_type=Output.DATAFRAME)

        if data.empty:
            return ""

        # Filter junk and extremely low confidence noise
        data = data[data.conf > 5]
        data = data[data.text.str.strip().str.len() > 0]

        if data.empty:
            return ""

        # 4. Row Reconstruction based on coordinates
        # Sort by top first to group rows
        data = data.sort_values(["top", "left"])

        row_groups = []
        if not data.empty:
            current_row = []
            # Use a tolerance for characters on the same line (approx 0.1 inch)
            y_tolerance = (dpi / 300) * 25

            # Initialize with first token
            prev_y = data.iloc[0]["top"]

            for _, row in data.iterrows():
                if (row["top"] - prev_y) > y_tolerance:
                    # Significant vertical jump, start new row
                    if current_row:
                        row_groups.append(current_row)
                    current_row = []

                current_row.append(row)
                # We stay on same row, but update prev_y to moving average or just current
                # Updating to current helps handle slight tilt/skew
                prev_y = row["top"]

            if current_row:
                row_groups.append(current_row)

        final_lines = []
        for row in row_groups:
            # Sort tokens in row by X coordinate
            sorted_row = sorted(row, key=lambda x: x["left"])

            line_parts = []
            prev_right = -1

            for word_data in sorted_row:
                token = str(word_data["text"]).strip()
                clean_token = clean_ocr_token(token)
                if not clean_token:
                    continue

                # Detect gaps for leader dots
                # Usually a gap of 120+ pixels (at 300dpi) indicates missing dots
                gap_threshold = (dpi / 300) * 140
                if prev_right != -1 and (word_data["left"] - prev_right) > gap_threshold:
                    if not line_parts[-1].endswith("..."):
                        line_parts.append("...")

                line_parts.append(clean_token)
                prev_right = word_data["left"] + word_data["width"]

            if line_parts:
                final_lines.append(" ".join(line_parts))

        return "\n".join(final_lines)

    except Exception:
        # Graceful fallback to native text
        return page.get_text("text") or ""
