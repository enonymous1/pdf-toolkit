import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets

from pdf_toolkit.compressor import compress_pdf, format_size

# --- Check for PyMuPDF (fitz) for PDF preview ---
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    PDF_PREVIEW_ERROR_MESSAGE = (
        "PyMuPDF (fitz) library not found. PDF preview will be disabled.\n"
        "Install it with: pip install PyMuPDF"
    )

# --- Stylesheets for Drop Area ---
STYLE_DROP_AREA_DEFAULT = """
    QLabel {
        border: 2px dashed #aaa; border-radius: 5px;
        background-color: #f0f0f0; color: #777; font-size: 12pt;
    }
    QLabel:hover { border-color: #777; background-color: #e8e8e8; }
"""
STYLE_DROP_AREA_VALID_PDF_SELECTED = """
    QLabel {
        border: 2px solid #2ecc71; border-radius: 5px; /* Solid green border */
        background-color: #e6ffe6; color: #27ae60; font-size: 12pt; /* Light green background, darker green text */
    }
"""
STYLE_DROP_AREA_INVALID_PDF_ATTEMPT = """
    QLabel {
        border: 2px solid #e74c3c; border-radius: 5px; /* Solid red border */
        background-color: #ffe6e6; color: #c0392b; font-size: 12pt; /* Light red background, darker red text */
    }
"""
STYLE_DROP_AREA_DRAG_OVER_VALID = """
    QLabel {
        border: 2px dashed #339933; border-radius: 5px; /* Dashed green for drag over */
        background-color: #e6ffe6; color: #339933; font-size: 12pt;
    }
"""
STYLE_PREVIEW_AREA_DEFAULT = """
    QLabel {
        border: 1px solid #ccc; background-color: #e0e0e0; color: #555;
        font-size: 10pt;
    }
"""


# --- Worker for running compression in a separate thread ---
class CompressionWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool, str, str)
    progress = QtCore.pyqtSignal(str)

    def __init__(
        self,
        input_path,
        output_path,
        method,
        gs_quality=None,
        pypdf_remove_meta=False,
        pypdf_compress_streams=True,
        parent=None,
    ):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.method = method
        self.gs_quality = gs_quality
        self.pypdf_remove_meta = pypdf_remove_meta
        self.pypdf_compress_streams = pypdf_compress_streams

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.progress.emit("Initializing compressor...")
            method = {"pypdf": "pypdf", "Ghostscript": "ghostscript"}.get(self.method, self.method)
            kwargs = {}
            if method == "pypdf":
                self.progress.emit("Compressing with pypdf...")
                kwargs = {
                    "remove_metadata": self.pypdf_remove_meta,
                    "compress_content_streams": self.pypdf_compress_streams,
                }
            elif method == "ghostscript":
                self.progress.emit(f"Compressing with Ghostscript ({self.gs_quality})...")
                kwargs = {"quality": self.gs_quality or "ebook"}
            elif method == "structural":
                self.progress.emit("Compressing structurally...")
            else:
                self.finished.emit(False, "Unknown method.", "")
                return
            result = compress_pdf(self.input_path, self.output_path, method, **kwargs)
            if result.success:
                message = (
                    f"{method} compression succeeded: "
                    f"{format_size(result.initial_size)} -> {format_size(result.final_size)} "
                    f"({result.reduction_pct:.1f}% saved)."
                )
            else:
                message = f"{method} compression failed: {result.error or 'unknown error'}"
            self.finished.emit(result.success, message, self.output_path if result.success else "")
        except Exception as e:
            self.finished.emit(False, f"Compression error: {e}", "")


# --- Main Application Window ---
class PdfDropWindow(QtWidgets.QMainWindow):
    pdfPathObtained = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_pdf_path = None
        self.current_preview_pixmap = None  # Store the original rendered pixmap
        self.compress_thread = None
        self.compression_worker = None
        self.preview_groupbox = None  # Initialize preview_groupbox attribute

        self.setWindowTitle("PDF Toolkit — Compressor & Preview (PyQt6)")
        self.setMinimumSize(500, 600)  # Increased size for preview
        self.setAcceptDrops(True)
        self._init_ui()
        self._create_toolbar()  # Create toolbar after UI elements

        if not PYMUPDF_AVAILABLE:
            QtWidgets.QMessageBox.warning(self, "Preview Unavailable", PDF_PREVIEW_ERROR_MESSAGE)

    def _init_ui(self):
        main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(main_widget)

        main_layout = QtWidgets.QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        top_section_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top_section_widget)
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(0, 0, 0, 0)

        welcome_label = QtWidgets.QLabel("Welcome to PDF Toolkit!", self)
        welcome_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        welcome_label.setFont(font)
        top_layout.addWidget(welcome_label)

        instruction_label = QtWidgets.QLabel("Drag & drop a PDF below, or click 'Browse'.", self)
        instruction_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instruction_label.setWordWrap(True)
        top_layout.addWidget(instruction_label)

        self.drop_area = QtWidgets.QLabel("Drag PDF Here", self)
        self.drop_area.setMinimumHeight(80)
        self.drop_area.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.drop_area.setStyleSheet(STYLE_DROP_AREA_DEFAULT)
        self.drop_area.setAcceptDrops(True)
        top_layout.addWidget(self.drop_area)

        browse_button = QtWidgets.QPushButton("Browse for PDF...", self)
        browse_button.setFixedHeight(35)
        browse_button.clicked.connect(self.open_file_dialog)
        top_layout.addWidget(browse_button)

        main_layout.addWidget(top_section_widget)

        # --- Preview Area ---
        self.preview_groupbox = QtWidgets.QGroupBox("PDF Preview (First Page)")  # Assign to self.
        preview_layout = QtWidgets.QVBoxLayout(self.preview_groupbox)

        self.preview_area_label = QtWidgets.QLabel("No PDF loaded for preview.", self)
        self.preview_area_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_area_label.setMinimumHeight(200)
        self.preview_area_label.setStyleSheet(STYLE_PREVIEW_AREA_DEFAULT)
        self.preview_area_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        preview_layout.addWidget(self.preview_area_label)
        main_layout.addWidget(self.preview_groupbox)

        bottom_section_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_section_widget)
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QtWidgets.QLabel("No file selected.", self)
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        bottom_layout.addWidget(self.status_label)

        self.compress_button = QtWidgets.QPushButton("Compress PDF", self)
        self.compress_button.setFixedHeight(35)
        self.compress_button.setEnabled(False)
        self.compress_button.clicked.connect(self.prompt_compression_settings)
        bottom_layout.addWidget(self.compress_button)

        main_layout.addWidget(bottom_section_widget)
        main_layout.addStretch(1)

        main_widget.setLayout(main_layout)
        self.update_preview_display()

    def _create_toolbar(self):
        """Creates the main toolbar with actions."""
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)  # Optional: prevent toolbar from being moved

        self.preview_action = QtGui.QAction("Preview", self)
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(True)  # Preview is visible by default
        self.preview_action.triggered.connect(self.toggle_preview_visibility)
        self.toolbar.addAction(self.preview_action)

        # You can add more actions here later, e.g., "Settings", "About"
        # self.toolbar.addSeparator()
        # settings_action = QtGui.QAction("Settings", self)
        # self.toolbar.addAction(settings_action)

    def toggle_preview_visibility(self, checked):
        """Shows or hides the PDF preview groupbox."""
        if self.preview_groupbox:  # Check if it has been initialized
            self.preview_groupbox.setVisible(checked)
            # If hiding, you might want to reclaim some space, though QVBoxLayout handles this
            # If showing, ensure preview is updated if a file is loaded
            if checked and self.current_selected_pdf_path:
                self.update_preview_display()

    def open_file_dialog(self):
        start_dir = (
            os.path.dirname(self.current_selected_pdf_path)
            if self.current_selected_pdf_path
            else ""
        )
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select a PDF file", start_dir, "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.process_selected_file(file_path)
        else:  # Dialog cancelled
            self.status_label.setText(
                "File selection cancelled. Previous selection (if any) retained."
            )
            # If no file was previously selected, ensure UI reflects "no file" state
            if not self.current_selected_pdf_path:
                self.drop_area.setStyleSheet(STYLE_DROP_AREA_DEFAULT)
                self.drop_area.setText("Drag PDF Here")
                self.render_and_cache_preview(None)  # Clear pixmap cache
                self.update_preview_display()  # Update display to show "No PDF loaded"

    def process_selected_file(self, file_path: str):
        if file_path and file_path.lower().endswith(".pdf"):
            self.current_selected_pdf_path = file_path
            self.status_label.setText(f"Selected: {os.path.basename(file_path)}")
            self.compress_button.setEnabled(True)
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_VALID_PDF_SELECTED)
            self.drop_area.setText(f"PDF Loaded:\n{os.path.basename(file_path)}")
            self.pdfPathObtained.emit(file_path)
            self.render_and_cache_preview(file_path)  # This will call update_preview_display
        else:
            QtWidgets.QMessageBox.warning(
                self, "Invalid File", "Please select or drop a valid PDF file."
            )
            self.status_label.setText("Invalid file type. Please select a PDF.")
            if not self.current_selected_pdf_path:
                self.compress_button.setEnabled(False)
                self.drop_area.setStyleSheet(STYLE_DROP_AREA_INVALID_PDF_ATTEMPT)
                self.drop_area.setText("Invalid File Type!")
                self.render_and_cache_preview(None)
            self.update_preview_display()  # Ensure preview reflects current state

    def render_and_cache_preview(self, file_path: str = None):
        self.current_preview_pixmap = None
        if not PYMUPDF_AVAILABLE:
            self.preview_area_label.setText("Preview unavailable (PyMuPDF missing).")
            self.update_preview_display()  # Call to clear any existing pixmap
            return
        if not file_path:
            self.preview_area_label.setText("No PDF loaded for preview.")
            self.update_preview_display()  # Call to clear any existing pixmap
            return

        try:
            doc = fitz.open(file_path)
            if doc.page_count > 0:
                page = doc.load_page(0)
                zoom = 150 / 72
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                qimage = QtGui.QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QtGui.QImage.Format.Format_RGB888,
                )
                self.current_preview_pixmap = QtGui.QPixmap.fromImage(qimage)
                self.preview_area_label.setText("")
            else:
                self.preview_area_label.setText("PDF has no pages.")
            doc.close()
        except Exception as e:
            self.preview_area_label.setText(f"Error rendering preview:\n{str(e)[:100]}")
            print(f"Error rendering PDF preview: {e}")
        self.update_preview_display()

    def update_preview_display(self):
        if (
            self.current_preview_pixmap and self.preview_groupbox.isVisible()
        ):  # Only update if visible
            self.preview_area_label.setPixmap(
                self.current_preview_pixmap.scaled(
                    self.preview_area_label.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview_area_label.setPixmap(QtGui.QPixmap())
            # Text for no preview should be set by render_and_cache_preview
            if not self.current_preview_pixmap and not self.preview_area_label.text():
                if not PYMUPDF_AVAILABLE:
                    self.preview_area_label.setText("Preview unavailable (PyMuPDF missing).")
                else:
                    self.preview_area_label.setText("No PDF loaded for preview.")

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        if self.preview_groupbox.isVisible():  # Only update if visible
            self.update_preview_display()

    def prompt_compression_settings(self):
        if not self.current_selected_pdf_path:
            QtWidgets.QMessageBox.warning(self, "No File", "Please select a PDF file first.")
            return

        methods = ["structural", "pypdf", "Ghostscript"]
        method, ok = QtWidgets.QInputDialog.getItem(
            self, "Choose Method", "Method:", methods, 0, False
        )
        if not ok or not method:
            return

        gs_quality = None
        if method == "Ghostscript":
            qualities = ["ebook", "screen", "printer"]
            gs_quality, ok = QtWidgets.QInputDialog.getItem(
                self, "Ghostscript Quality", "Preset:", qualities, 0, False
            )
            if not ok or not gs_quality:
                return

        self.get_output_file_path_and_compress(method, gs_quality, False, True)

    def get_output_file_path_and_compress(
        self, method, gs_quality, pypdf_rm_meta, pypdf_comp_streams
    ):
        input_dir = os.path.dirname(self.current_selected_pdf_path)
        base, ext = os.path.splitext(os.path.basename(self.current_selected_pdf_path))
        tag = f"{method.lower()}{'_' + gs_quality if gs_quality else ''}"
        default_filename = os.path.join(input_dir, f"{base}_compressed_{tag}{ext}")
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save As...", default_filename, "PDF Files (*.pdf)"
        )

        if output_path:
            self.initiate_compression_thread(
                self.current_selected_pdf_path,
                output_path,
                method,
                gs_quality,
                pypdf_rm_meta,
                pypdf_comp_streams,
            )
        else:
            self.status_label.setText("Save operation cancelled.")

    def initiate_compression_thread(
        self, in_path, out_path, method, gs_quality, pypdf_rm_meta, pypdf_comp_streams
    ):
        if self.compress_thread and self.compress_thread.isRunning():
            QtWidgets.QMessageBox.information(self, "Busy", "Compression in progress.")
            return
        self.compress_button.setEnabled(False)
        self.status_label.setText("Preparing compression...")
        self.compress_thread = QtCore.QThread(self)
        self.compression_worker = CompressionWorker(
            in_path, out_path, method, gs_quality, pypdf_rm_meta, pypdf_comp_streams
        )
        self.compression_worker.moveToThread(self.compress_thread)
        self.compress_thread.started.connect(self.compression_worker.run)
        self.compression_worker.finished.connect(self.handle_compression_finished)
        self.compression_worker.progress.connect(self.update_status_label_slot)
        self.compression_worker.finished.connect(self.compress_thread.quit)
        self.compress_thread.finished.connect(self.compress_thread.deleteLater)
        self.compression_worker.finished.connect(self.compression_worker.deleteLater)
        self.compress_thread.start()

    @QtCore.pyqtSlot(str)
    def update_status_label_slot(self, message):
        self.status_label.setText(message)

    @QtCore.pyqtSlot(bool, str, str)
    def handle_compression_finished(self, success, message, out_path):
        self.compress_button.setEnabled(self.current_selected_pdf_path is not None)
        self.status_label.setText(message or "Compression finished.")
        if success:
            QtWidgets.QMessageBox.information(self, "Success", f"{message}\nSaved to:\n{out_path}")
            if self.current_selected_pdf_path:
                self.drop_area.setText(
                    f"Last compressed:\n{os.path.basename(self.current_selected_pdf_path)}"
                )
                self.drop_area.setStyleSheet(STYLE_DROP_AREA_VALID_PDF_SELECTED)
        else:
            QtWidgets.QMessageBox.critical(self, "Failed", message)
            if self.current_selected_pdf_path:
                self.drop_area.setStyleSheet(STYLE_DROP_AREA_INVALID_PDF_ATTEMPT)
                self.drop_area.setText(
                    f"Error with:\n{os.path.basename(self.current_selected_pdf_path)}"
                )
        self.compress_thread = None
        self.compression_worker = None

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        mime = event.mimeData()
        if mime.hasUrls() and any(
            u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf") for u in mime.urls()
        ):
            event.acceptProposedAction()
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_DRAG_OVER_VALID)
        else:
            event.ignore()
            self.drop_area.setStyleSheet(
                STYLE_DROP_AREA_DEFAULT
                if not self.current_selected_pdf_path
                else STYLE_DROP_AREA_VALID_PDF_SELECTED
            )

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        mime = event.mimeData()
        if mime.hasUrls() and any(
            u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf") for u in mime.urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        if self.current_selected_pdf_path:
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_VALID_PDF_SELECTED)
            self.drop_area.setText(
                f"PDF Loaded:\n{os.path.basename(self.current_selected_pdf_path)}"
            )
        else:
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_DEFAULT)
            self.drop_area.setText("Drag PDF Here")
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            pdf_files = [
                u.toLocalFile()
                for u in mime.urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")
            ]
            if pdf_files:
                self.process_selected_file(pdf_files[0])
                event.acceptProposedAction()
                return
        QtWidgets.QMessageBox.warning(self, "Invalid Drop", "Please drop only PDF files.")
        if self.current_selected_pdf_path:
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_VALID_PDF_SELECTED)
            self.drop_area.setText(
                f"PDF Loaded:\n{os.path.basename(self.current_selected_pdf_path)}"
            )
        else:
            self.drop_area.setStyleSheet(STYLE_DROP_AREA_DEFAULT)
            self.drop_area.setText("Drag PDF Here")
        event.ignore()

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self.compress_thread and self.compress_thread.isRunning():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Exit",
                "Compression in progress. Exit anyway?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.compress_thread.quit()
                self.compress_thread.wait(2000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = PdfDropWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
