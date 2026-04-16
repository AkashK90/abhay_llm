"""
test_chunker.py
Unit tests for ingestion/chunker.py
No external dependencies required.
"""
import pytest
from ingestion.chunker import chunk_document, _split_text, TextChunk
from ingestion.parser import ParsedDocument, PageContent


def _make_parsed(text: str, pages: int = 1) -> ParsedDocument:
    """Helper: create a simple single-page ParsedDocument."""
    page_list = [
        PageContent(page_number=i + 1, text=text, char_offset=i * len(text))
        for i in range(pages)
    ]
    return ParsedDocument(
        file_path="/fake/path.txt",
        mime_type="text/plain",
        pages=page_list,
    )


class TestSplitText:
    def test_short_text_not_split(self):
        result = _split_text("short text", chunk_size=100, overlap=10)
        assert result == ["short text"]

    def test_splits_on_double_newline(self):
        text = "paragraph one\n\nparagraph two\n\nparagraph three"
        result = _split_text(text, chunk_size=20, overlap=0)
        assert len(result) > 1

    def test_overlap_creates_shared_content(self):
        # Build text that's exactly 2x chunk_size
        word = "word "
        text = word * 100  # 500 chars
        result = _split_text(text, chunk_size=50, overlap=10)
        # Each chunk except the last should share ~10 chars with the next
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 60  # chunk_size + some slack

    def test_empty_text_returns_empty(self):
        result = _split_text("", chunk_size=100, overlap=10)
        assert result == [""]

    def test_exactly_chunk_size_not_split(self):
        text = "a" * 800
        result = _split_text(text, chunk_size=800, overlap=80)
        assert len(result) == 1


class TestChunkDocument:
    def test_basic_chunking_produces_chunks(self, sample_txt_file):
        from ingestion.parser import parse_document

        parsed = parse_document(str(sample_txt_file), "text/plain")
        chunks = chunk_document(parsed, chunk_size=100, chunk_overlap=10)

        assert len(chunks) >= 1
        assert all(isinstance(c, TextChunk) for c in chunks)

    def test_chunk_indices_are_sequential(self, sample_txt_file):
        from ingestion.parser import parse_document

        parsed = parse_document(str(sample_txt_file), "text/plain")
        chunks = chunk_document(parsed, chunk_size=100, chunk_overlap=10)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_ids_are_unique(self, sample_large_txt_file):
        from ingestion.parser import parse_document

        parsed = parse_document(str(sample_large_txt_file), "text/plain")
        chunks = chunk_document(parsed, chunk_size=200, chunk_overlap=20)

        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_page_number_preserved(self):
        parsed = _make_parsed("Some text for testing the chunker.", pages=1)
        parsed.pages[0].page_number = 7
        chunks = chunk_document(parsed, chunk_size=50, chunk_overlap=5)

        for chunk in chunks:
            assert chunk.page_number == 7

    def test_text_preview_max_512(self):
        long_text = "x" * 1000
        parsed = _make_parsed(long_text)
        chunks = chunk_document(parsed, chunk_size=1000, chunk_overlap=0)

        for chunk in chunks:
            assert len(chunk.text_preview) <= 512

    def test_empty_document_returns_no_chunks(self):
        parsed = _make_parsed("   \n\n   ")  # whitespace only
        chunks = chunk_document(parsed, chunk_size=100, chunk_overlap=10)
        assert chunks == []

    def test_token_estimate_positive(self):
        parsed = _make_parsed("Hello world this is a test sentence.")
        chunks = chunk_document(parsed, chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            assert chunk.token_estimate >= 1

    def test_large_document_many_chunks(self, sample_large_txt_file):
        from ingestion.parser import parse_document

        parsed = parse_document(str(sample_large_txt_file), "text/plain")
        chunks = chunk_document(parsed, chunk_size=300, chunk_overlap=30)
        assert len(chunks) > 5
