from pathlib import Path
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog,
    QListWidget, QMessageBox, QProgressBar
)

from pdf_to_image.core.settings import load_settings, save_settings
from pdf_to_image.core.converter import find_pdfs_recursively, convert_pdf_to_images

logger = logging.getLogger(__name__)

class ConversionWorker(QThread):
    progress_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str, str)
    finished_successfully = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, pdf_files, output_dir, out_format):
        super().__init__()
        self.pdf_files = pdf_files
        self.output_dir = output_dir
        self.out_format = out_format
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        total_files = len(self.pdf_files)
        for i, pdf_path in enumerate(self.pdf_files):
            if self.is_cancelled:
                break
            try:
                base_progress = int((i / total_files) * 100)

                def page_progress(current_page, total_pages):
                    if self.is_cancelled:
                        return False
                    file_progress_percent = (current_page / total_pages) * (100 / total_files)
                    self.progress_updated.emit(base_progress + int(file_progress_percent))
                    return True

                success = convert_pdf_to_images(pdf_path, self.output_dir, self.out_format, progress_callback=page_progress)
                if success is False:
                    break
            except Exception as e:
                self.error_occurred.emit(str(pdf_path), str(e))

        if self.is_cancelled:
            self.cancelled.emit()
        else:
            self.progress_updated.emit(100)
            self.finished_successfully.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF to Image Converter")
        self.resize(700, 500)

        self.settings = load_settings()
        self.pdf_files_to_convert = []

        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 控制面板：格式與輸出路徑
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("輸出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "bmp", "tiff"])
        self.format_combo.setCurrentText(self.settings.get("output_format", "jpg"))
        self.format_combo.currentTextChanged.connect(self.save_current_settings)
        control_layout.addWidget(self.format_combo)

        self.output_btn = QPushButton("設定輸出資料夾")
        self.output_btn.clicked.connect(self.select_output_dir)
        control_layout.addWidget(self.output_btn)

        self.output_label = QLabel(self.settings.get("output_path"))
        control_layout.addWidget(self.output_label)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 檔案清單區域
        layout.addWidget(QLabel("請將 PDF 檔案或資料夾拖拉至下方清單，或點擊上傳:"))
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

        # 進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 按鈕區域
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self.clear_list)
        self.convert_btn = QPushButton("開始轉換 (Batch)")
        self.convert_btn.clicked.connect(self.convert_files)
        self.cancel_btn = QPushButton("取消轉換")
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        self.cancel_btn.setEnabled(False)

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.convert_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "選擇輸出資料夾", self.settings.get("output_path", "")
        )
        if dir_path:
            self.settings["output_path"] = dir_path
            self.output_label.setText(dir_path)
            self.save_current_settings()

    def save_current_settings(self):
        self.settings["output_format"] = self.format_combo.currentText()
        save_settings(self.settings)

    def clear_list(self):
        self.file_list.clear()
        self.pdf_files_to_convert.clear()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]

        # 尋找所有遞迴的 PDF
        found_pdfs = find_pdfs_recursively(paths)
        for pdf in found_pdfs:
            if pdf not in self.pdf_files_to_convert:
                self.pdf_files_to_convert.append(pdf)
                self.file_list.addItem(str(pdf))

        # 儲存最後上傳路徑的紀錄
        if paths:
            self.settings["last_upload_path"] = str(Path(paths[0]).parent)
            self.save_current_settings()

    def convert_files(self):
        if not self.pdf_files_to_convert:
            QMessageBox.warning(self, "警告", "沒有要轉換的 PDF 檔案。")
            return

        output_dir = Path(self.settings.get("output_path"))
        out_format = self.format_combo.currentText()

        self.convert_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        logger.info(f"準備開始批次轉換，共 {len(self.pdf_files_to_convert)} 個檔案")

        self.worker = ConversionWorker(self.pdf_files_to_convert, output_dir, out_format)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.error_occurred.connect(self.on_conversion_error)
        self.worker.finished_successfully.connect(self.on_conversion_finished)
        self.worker.cancelled.connect(self.on_conversion_cancelled)
        self.worker.start()

    def cancel_conversion(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("正在取消...")
            self.worker.cancel()

    def on_conversion_cancelled(self):
        self.convert_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("取消轉換")
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "已取消", "轉換作業已被使用者取消。")
        logger.info("批次轉換已被使用者取消")

    def on_conversion_error(self, file_path, error_msg):
        logger.error(f"檔案 {Path(file_path).name} 遇到錯誤: {error_msg}")
        QMessageBox.critical(self, "錯誤", f"轉換 {Path(file_path).name} 失敗:\n{error_msg}")

    def on_conversion_finished(self):
        self.convert_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.information(self, "完成", "所有 PDF 轉換完成！")
        self.clear_list()
        self.progress_bar.setVisible(False)