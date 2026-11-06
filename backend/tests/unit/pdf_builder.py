"""Build tiny, hand-rolled PDF byte strings for parser tests.

Not a general-purpose PDF writer — just enough valid structure (correct
xref byte offsets, one font, one content stream per page) for `pypdf` to
read back the exact text we put in. Keeps the parser tests free of any new
PDF-generation dependency.
"""


def build_minimal_pdf(page_texts: list[str]) -> bytes:
    """Return bytes for a PDF with one page per string in `page_texts`."""
    page_count = len(page_texts)
    font_obj_num = 3 + page_count

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(page_count),
    ]
    objects.extend(_page_object(font_obj_num, index) for index in range(page_count))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.extend(_content_stream_object(text) for text in page_texts)

    return _assemble_pdf(objects)


def _pages_object(page_count: int) -> bytes:
    kids = " ".join(f"{3 + i} 0 R" for i in range(page_count))
    return f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode()


def _page_object(font_obj_num: int, index: int) -> bytes:
    contents_obj_num = font_obj_num + 1 + index
    return (
        f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
        f"/MediaBox [0 0 200 200] /Contents {contents_obj_num} 0 R >>"
    ).encode()


def _content_stream_object(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    return f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"


def _assemble_pdf(objects: list[bytes]) -> bytes:
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    pdf += f"startxref\n{xref_offset}\n%%EOF".encode()
    return bytes(pdf)
