from pathlib import Path
import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

def find_pdfs_recursively(paths: list[str]) -> list[Path]:
    """尋找給定路徑下（包含資料夾內）所有的 PDF 檔案"""
    pdf_files = []
    for path_str in paths:
        p = Path(path_str)
        if p.is_file() and p.suffix.lower() == ".pdf":
            pdf_files.append(p)
        elif p.is_dir():
            # recursively 的拜訪資料夾內所有 pdf
            pdf_files.extend(p.rglob("*.pdf"))

    logger.info(f"找到 {len(pdf_files)} 個 PDF 檔案")
    return pdf_files

def convert_pdf_to_images(pdf_path: Path, output_dir: Path, output_format: str = "jpg", progress_callback=None):
    """將指定的 PDF 轉換成圖片並儲存到輸出資料夾"""
    logger.info(f"開始轉換檔案: {pdf_path.name}")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            # 取得頁面的像素圖形 (預設 150 dpi)
            pix = page.get_pixmap(dpi=150)

            output_filename = output_dir / f"{pdf_path.stem}_page_{page_num + 1}.{output_format}"
            pix.save(str(output_filename))

            if progress_callback:
                if progress_callback(page_num + 1, total_pages) is False:
                    logger.info(f"轉換中斷: {pdf_path.name}")
                    doc.close()
                    return False

        doc.close()
        logger.info(f"成功完成轉換: {pdf_path.name} (共 {total_pages} 頁)")
        return True
    except Exception as e:
        logger.error(f"轉換檔案 {pdf_path.name} 失敗: {e}", exc_info=True)
        raise e