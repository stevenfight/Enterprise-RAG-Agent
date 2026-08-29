"""v7 PDF 输入校验的确定性测试。"""

import fitz


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def test_valid_pdf_returns_physical_page_count():
    from src.pdf_validation import inspect_pdf_bytes

    result = inspect_pdf_bytes(_pdf_bytes(2))

    assert result.valid is True
    assert result.status == "valid"
    assert result.physical_page_count == 2


def test_non_pdf_magic_is_rejected_before_parser():
    from src.pdf_validation import inspect_pdf_bytes

    result = inspect_pdf_bytes(b"not a pdf")

    assert result.valid is False
    assert result.status == "invalid_magic"
    assert result.physical_page_count is None


def test_truncated_pdf_is_explicitly_unreadable():
    from src.pdf_validation import inspect_pdf_bytes

    result = inspect_pdf_bytes(b"%PDF-1.7\ntruncated")

    assert result.valid is False
    assert result.status == "unreadable"
    assert result.physical_page_count is None


def test_encrypted_pdf_is_rejected_without_parser_queueing():
    from src.pdf_validation import inspect_pdf_bytes

    document = fitz.open()
    document.new_page()
    encrypted_pdf = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()

    result = inspect_pdf_bytes(encrypted_pdf)

    assert result.valid is False
    assert result.status == "unsupported_encrypted"
    assert result.physical_page_count is None
