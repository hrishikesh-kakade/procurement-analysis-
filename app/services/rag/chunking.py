import re

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = 900, overlap_chars: int = 120) -> list[str]:
    """Split on paragraph boundaries, packing paragraphs up to max_chars with a small overlap.

    Markdown headings stay attached to the paragraph that follows them.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    merged: list[str] = []
    for paragraph in paragraphs:
        if merged and merged[-1].lstrip().startswith("#") and "\n" not in merged[-1]:
            merged[-1] = f"{merged[-1]}\n{paragraph}"
        else:
            merged.append(paragraph)

    pieces: list[str] = []
    for paragraph in merged:
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        current = ""
        for sentence in _SENTENCE.split(paragraph):
            if current and len(current) + len(sentence) + 1 > max_chars:
                pieces.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            pieces.append(current)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail} {piece}".strip() if tail else piece
        else:
            current = f"{current}\n\n{piece}".strip() if current else piece
    if current:
        chunks.append(current)
    return chunks
