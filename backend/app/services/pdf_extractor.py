"""업로드 PDF를 검증하고 페이지별 텍스트를 만든다. 텍스트가 없는 페이지만 OCR한다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MIN_PAGE_TEXT_CHARS = 50
OCR_DPI = 300
MAX_PAGE_PIXELS = 25_000_000
MAX_PAGE_SIDE_PIXELS = 10_000
MAX_PAGE_TEXT_CHARS = 200_000
MAX_DOCUMENT_TEXT_CHARS = 2_000_000


class PdfError(Exception):
    status_code = 400


class PdfTooLarge(PdfError):
    status_code = 413


class PdfContentError(PdfError):
    status_code = 422


class OcrUnavailable(PdfError):
    status_code = 503


@dataclass(frozen=True)
class ExtractedPage:
    page_no: int
    text: str
    method: str  # "text" | "ocr"


@dataclass
class ExtractedPdf:
    pages: list[ExtractedPage]
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    def processing(self) -> dict:
        return {
            "pages": len(self.pages),
            "text_pages": sum(page.method == "text" for page in self.pages),
            "ocr_pages": [page.page_no for page in self.pages if page.method == "ocr"],
            "warnings": list(self.warnings),
        }


def _text_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _ocr_page(page) -> str:
    try:
        tessdata = pymupdf.get_tessdata()
        textpage = page.get_textpage_ocr(language="kor+eng", dpi=OCR_DPI, full=True, tessdata=tessdata)
        return page.get_text("text", textpage=textpage, sort=True).strip()
    except Exception as exc:
        raise OcrUnavailable("OCR 실행 환경(Tesseract 한국어 데이터)을 확인할 수 없습니다.") from exc


def extract_pdf(data: bytes) -> ExtractedPdf:
    if len(data) > MAX_PDF_BYTES:
        raise PdfTooLarge("PDF는 파일당 20MB 이하여야 합니다.")
    if not data.startswith(b"%PDF-"):
        raise PdfError("PDF 파일 형식이 아닙니다.")

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfError("손상되었거나 읽을 수 없는 PDF입니다.") from exc

    try:
        if document.needs_pass:
            raise PdfError("암호화된 PDF는 분석할 수 없습니다.")
        if document.page_count == 0:
            raise PdfContentError("내용이 없는 PDF입니다.")
        if document.page_count > MAX_PDF_PAGES:
            raise PdfTooLarge("PDF는 문서당 50페이지 이하여야 합니다.")

        pages: list[ExtractedPage] = []
        warnings: list[str] = []
        total_text_chars = 0
        for index, page in enumerate(document):
            width = int(page.rect.width / 72 * OCR_DPI)
            height = int(page.rect.height / 72 * OCR_DPI)
            if width > MAX_PAGE_SIDE_PIXELS or height > MAX_PAGE_SIDE_PIXELS or width * height > MAX_PAGE_PIXELS:
                raise PdfTooLarge(f"{index + 1}페이지 크기가 너무 커서 안전하게 처리할 수 없습니다.")
            text = page.get_text("text", sort=True).strip()
            method = "text"
            if _text_length(text) < MIN_PAGE_TEXT_CHARS:
                text = _ocr_page(page)
                method = "ocr"
                if _text_length(text) < MIN_PAGE_TEXT_CHARS:
                    warnings.append(f"{index + 1}페이지에서 충분한 글자를 읽지 못했습니다.")
            if len(text) > MAX_PAGE_TEXT_CHARS:
                raise PdfTooLarge(f"{index + 1}페이지의 텍스트가 너무 많습니다.")
            total_text_chars += len(text)
            if total_text_chars > MAX_DOCUMENT_TEXT_CHARS:
                raise PdfTooLarge("PDF의 전체 텍스트가 너무 많습니다.")
            pages.append(ExtractedPage(index + 1, text, method))

        if not any(_text_length(page.text) for page in pages):
            raise PdfContentError("PDF에서 분석할 텍스트를 읽지 못했습니다.")
        return ExtractedPdf(pages, warnings)
    finally:
        document.close()
