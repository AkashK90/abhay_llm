"""
chunker.py
Splits a ParsedDocument into overlapping text chunks suitable for embedding.
Preserves page_number metadata per chunk.
"""
from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field

from ingestion.parser import ParsedDocument, PageContent

logger = logging.getLogger(__name__)

# Separators tried in order — prefer paragraph breaks, fall back to sentences/words
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@dataclass
class TextChunk:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chunk_index: int = 0
    page_number: int | None = None
    char_offset: int = 0
    text: str = ""

    @property
    def text_preview(self) -> str:
        """First 512 chars for DB storage."""
        return self.text[:512]

    @property
    def token_estimate(self) -> int:
        """Rough token estimate: 1 token ≈ 4 chars."""
        return max(1, len(self.text) // 4)


def chunk_document(
    parsed: ParsedDocument,
    chunk_size: int = 800,
    chunk_overlap: int = 80,
) -> list[TextChunk]:
    """
    Chunk a ParsedDocument into overlapping TextChunks.
    Iterates pages so that page_number is preserved per chunk.
    """
    chunks: list[TextChunk] = []
    global_char_offset = 0

    for page in parsed.pages:
        page_chunks = _split_text(
            text=page.text,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )
        for raw_chunk in page_chunks:
            if not raw_chunk.strip():
                continue
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    page_number=page.page_number,
                    char_offset=global_char_offset + page.char_offset,
                    text=raw_chunk.strip(),
                )
            )
        global_char_offset += len(page.text)

    logger.info(
        "Chunked '%s' → %d chunks (size=%d overlap=%d)",
        parsed.file_path,
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Recursive character splitter.
    Tries each separator in _SEPARATORS, falling back to the next
    when a split would produce chunks that are still too large.
    """
    return _recursive_split(text, chunk_size, overlap, _SEPARATORS)


def _recursive_split(
    text: str,
    chunk_size: int,
    overlap: int,
    separators: list[str],
) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    separator = ""
    remaining_separators: list[str] = []

    # Pick the first separator that actually appears in the text
    for i, sep in enumerate(separators):
        if sep == "" or sep in text:
            separator = sep
            remaining_separators = separators[i + 1 :]
            break

    splits = text.split(separator) if separator else list(text)
    good_splits: list[str] = []
    current: list[str] = []
    current_len = 0

    for split in splits:
        split_len = len(split)
        if current_len + split_len + len(separator) > chunk_size and current:
            merged = separator.join(current)
            if merged:
                # Recurse only if a single piece is still too large
                if len(merged) > chunk_size and remaining_separators:
                    good_splits.extend(
                        _recursive_split(merged, chunk_size, overlap, remaining_separators)
                    )
                else:
                    good_splits.append(merged)
            # Keep overlap from the tail of current
            overlap_text = _tail_text(current, separator, overlap)
            current = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)

        current.append(split)
        current_len += split_len + len(separator)

    if current:
        merged = separator.join(current)
        if merged:
            good_splits.append(merged)

    return good_splits


def _tail_text(parts: list[str], separator: str, target_len: int) -> str:
    """Return the trailing text of joined parts up to target_len chars."""
    tail = separator.join(parts)
    return tail[-target_len:] if len(tail) > target_len else tail
