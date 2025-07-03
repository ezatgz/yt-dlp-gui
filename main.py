import sys
import os
import json
import yt_dlp
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QStatusBar, QFileDialog, QTabWidget, QLabel,
    QListWidget, QListWidgetItem, QCheckBox, QDialog, QMessageBox,
    QRadioButton, QStyle, QGroupBox
)
from PySide6.QtCore import QThread, Signal, Slot, QSettings, Qt, QTranslator, QLocale, QEvent
from PySide6.QtGui import QPixmap, QIcon, QFont, QAction, QActionGroup

# --- 资源路径解析函数 ---
def resolve_path(path):
    """获取资源的绝对路径，兼容开发环境和PyInstaller打包环境"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        base_path = sys._MEIPASS
    else:
        # 如果是直接运行的 .py
        base_path = os.path.abspath(".")
    return os.path.join(base_path, path)

# --- 全局翻译器实例 ---
translator = QTranslator()

# --- 主窗口 / Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.settings = QSettings("MyCompany", "YtDlpGUI")
        
        self.init_ui()
        self.create_language_menu()
        self.apply_styles()
        self.update_settings_display()
        self.retranslate_ui()

        self.worker = None
        self.thumb_worker = None

    def init_ui(self):
        # --- 已修改: 设置自定义主窗口图标 ---
        # --- MODIFIED: Set custom main window icon ---
        self.setWindowIcon(QIcon(resolve_path("icons/layers.svg")))
        
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("")
        self.language_menu = self.menu_bar.addMenu("")
        
        self.settings_action = self.file_menu.addAction("")
        self.settings_action.triggered.connect(self.open_settings_dialog)
        
        self.file_menu.addSeparator()
        
        self.exit_action = self.file_menu.addAction("")
        self.exit_action.triggered.connect(self.close)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.fetch_button = QPushButton()
        # --- 已修改: 设置自定义按钮图标 ---
        self.fetch_button.setIcon(QIcon(resolve_path("icons/refresh-cw.svg")))
        self.fetch_button.clicked.connect(self.fetch_video_info)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_button)
        main_layout.addLayout(url_layout)

        info_layout = QHBoxLayout()
        
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setFixedWidth(320)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid #cccccc; background-color: #f0f0f0; border-radius: 5px;")
        
        self.video_title_label = QLabel()
        self.video_title_label.setWordWrap(True)
        self.video_title_label.setAlignment(Qt.AlignTop)

        left_panel_layout.addWidget(self.thumbnail_label)
        left_panel_layout.addWidget(self.video_title_label)
        left_panel_layout.addStretch()

        info_layout.addWidget(left_panel)

        self.tabs = QTabWidget()
        self.video_table = QTableWidget()
        self.audio_table = QTableWidget()
        self.subtitle_list = QListWidget()
        
        # --- 已修改: 设置自定义标签页图标 ---
        self.tabs.addTab(self.video_table, QIcon(resolve_path("icons/video.svg")), "")
        self.tabs.addTab(self.audio_table, QIcon(resolve_path("icons/volume-2.svg")), "")
        self.tabs.addTab(self.subtitle_list, QIcon(resolve_path("icons/file-text.svg")), "")
        
        info_layout.addWidget(self.tabs)
        info_layout.setSpacing(15)

        main_layout.addLayout(info_layout)

        self.download_groupbox = QGroupBox()
        download_group_layout = QVBoxLayout(self.download_groupbox)
        
        output_layout = QHBoxLayout()
        self.output_path_input = QLineEdit()
        self.browse_button = QPushButton()
        # --- 已修改: 设置自定义按钮图标 ---
        self.browse_button.setIcon(QIcon(resolve_path("icons/folder.svg")))
        self.browse_button.clicked.connect(self.browse_output_path)
        self.save_to_label = QLabel()
        output_layout.addWidget(self.save_to_label)
        output_layout.addWidget(self.output_path_input)
        output_layout.addWidget(self.browse_button)
        download_group_layout.addLayout(output_layout)

        extra_options_layout = QHBoxLayout()
        self.keep_files_checkbox = QCheckBox()
        extra_options_layout.addWidget(self.keep_files_checkbox)
        extra_options_layout.addStretch()
        self.cookie_path_label = QLabel()
        extra_options_layout.addWidget(self.cookie_path_label)
        download_group_layout.addLayout(extra_options_layout)

        self.download_button = QPushButton()
        # --- 已修改: 设置自定义按钮图标 ---
        self.download_button.setIcon(QIcon(resolve_path("icons/download.svg")))
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setEnabled(False)
        download_group_layout.addWidget(self.download_button)

        main_layout.addWidget(self.download_groupbox)

        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
        
    def retranslate_ui(self):
        self.setWindowTitle(self.tr("YT-DLP 图形界面下载器"))
        self.setGeometry(100, 100, 1200, 800)

        self.file_menu.setTitle(self.tr("文件(&F)"))
        self.language_menu.setTitle(self.tr("语言(&L)"))
        self.settings_action.setText(self.tr("设置(&S)..."))
        self.exit_action.setText(self.tr("退出(&X)"))

        self.url_input.setPlaceholderText(self.tr("在此处粘贴 YouTube 视频 URL..."))
        self.fetch_button.setText(self.tr(" 获取信息"))
        
        self.thumbnail_label.setText(self.tr("视频封面将在此处显示"))
        self.video_title_label.setText(self.tr("视频标题"))
        
        self.video_table_headers = [self.tr("选择"), self.tr("ID"), self.tr("格式"), self.tr("分辨率"), self.tr("帧率"), self.tr("编码"), self.tr("大小 (MB)")]
        self.audio_table_headers = [self.tr("选择"), self.tr("ID"), self.tr("格式"), self.tr("码率 (kbps)"), self.tr("编码"), self.tr("大小 (MB)")]
        self.create_table(self.video_table, self.video_table_headers)
        self.create_table(self.audio_table, self.audio_table_headers)
        
        self.tabs.setTabText(0, self.tr("视频轨道"))
        self.tabs.setTabText(1, self.tr("音频轨道"))
        self.tabs.setTabText(2, self.tr("字幕"))

        self.download_groupbox.setTitle(self.tr("下载选项与操作"))
        self.output_path_input.setPlaceholderText(self.tr("选择保存路径..."))
        self.browse_button.setText(self.tr(" 浏览..."))
        self.save_to_label.setText(self.tr("保存到:"))
        self.keep_files_checkbox.setText(self.tr("保留原始音视频文件"))
        self.download_button.setText(self.tr(" 开始下载"))
        self.status_bar.showMessage(self.tr("准备就绪"))
        self.update_settings_display()


    def apply_styles(self):
        font = QFont("Microsoft YaHei UI", 10)
        QApplication.setFont(font)

        title_font = QFont("Microsoft YaHei UI", 12, QFont.Bold)
        self.video_title_label.setFont(title_font)

        groupbox_font = QFont("Microsoft YaHei UI", 10, QFont.Bold)
        self.download_groupbox.setFont(groupbox_font)
        
        header_font = QFont()
        header_font.setBold(True)
        self.video_table.horizontalHeader().setFont(header_font)
        self.audio_table.horizontalHeader().setFont(header_font)

        button_style = "QPushButton { padding: 5px 10px; border-radius: 3px; }"
        self.fetch_button.setStyleSheet(button_style)
        self.browse_button.setStyleSheet(button_style)
        self.download_button.setStyleSheet("padding: 8px;")
        
        self.cookie_path_label.setStyleSheet("color: grey; font-size: 9pt;")

    def create_language_menu(self):
        self.lang_action_group = QActionGroup(self)
        self.lang_action_group.setExclusive(True)

        lang_map = { "en_US": "English", "zh_CN": "简体中文" }
        
        translations_path = resolve_path("translations")
        if not os.path.exists(translations_path):
            print(f"警告: 翻译文件夹未找到于: {translations_path}")
            return

        current_lang = self.settings.value("language", QLocale.system().name())

        for filename in os.listdir(translations_path):
            if filename.endswith(".qm"):
                locale = filename.replace("app_", "").replace(".qm", "")
                lang_name = lang_map.get(locale, locale)
                
                action = QAction(lang_name, self)
                action.setCheckable(True)
                action.setData(locale)
                
                self.language_menu.addAction(action)
                self.lang_action_group.addAction(action)

                if locale == current_lang:
                    action.setChecked(True)

        self.lang_action_group.triggered.connect(self.switch_language)

    @Slot(QAction)
    def switch_language(self, action):
        locale = action.data()
        self.settings.setValue("language", locale)
        
        global translator
        app = QApplication.instance()
        app.removeTranslator(translator)
        if translator.load(os.path.join(resolve_path("translations"), f"app_{locale}.qm")):
            app.installTranslator(translator)
        else:
             print(f"警告: 未能加载语言文件: app_{locale}.qm")


    def update_settings_display(self):
        cookie_path = self.settings.value("cookie_path", "")
        if cookie_path:
            filename = os.path.basename(cookie_path)
            self.cookie_path_label.setText(f"Cookie: {filename}")
            self.cookie_path_label.setToolTip(cookie_path)
        else:
            self.cookie_path_label.setText(self.tr("Cookie: 未设置"))
            self.cookie_path_label.setToolTip("")

    def create_table(self, table, headers):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        return table

    def browse_output_path(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("选择保存文件夹"))
        if path:
            self.output_path_input.setText(path)

    @Slot()
    def fetch_video_info(self):
        url = self.url_input.text()
        if not url:
            self.status_bar.showMessage(self.tr("错误: 请先输入URL。"))
            return

        self.set_ui_enabled(False)
        self.status_bar.showMessage(self.tr("正在获取视频信息，请稍候..."))
        self.progress_bar.setRange(0, 0)

        cookie_path = self.settings.value("cookie_path", "")

        self.worker = InfoWorker(url, cookie_path)
        self.worker.info_ready.connect(self.populate_info)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    @Slot(dict)
    def populate_info(self, info):
        self.status_bar.showMessage(self.tr("信息获取成功！"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_ui_enabled(True)
        self.download_button.setEnabled(True)

        self.video_title_label.setText(info.get('title', 'N/A'))
        self._current_info = info

        self.populate_video_table(info.get('formats', []))
        self.populate_audio_table(info.get('formats', []))
        self.populate_subtitle_list(info.get('subtitles', {}), info.get('automatic_captions', {}))

        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            self.thumb_worker = ThumbnailWorker(thumbnail_url)
            self.thumb_worker.image_ready.connect(self.set_thumbnail)
            self.thumb_worker.start()

    def populate_video_table(self, formats):
        self.video_table.setRowCount(0)
        video_formats = sorted(
            [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none'],
            key=lambda x: x.get('height', 0), reverse=True
        )
        for f in video_formats:
            row_position = self.video_table.rowCount()
            self.video_table.insertRow(row_position)
            
            radio_button = QRadioButton()
            cell_widget = QWidget()
            layout = QHBoxLayout(cell_widget)
            layout.addWidget(radio_button)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0,0,0,0)
            
            filesize_mb = (f.get('filesize') or f.get('filesize_approx') or 0) / (1024 * 1024)
            
            self.video_table.setCellWidget(row_position, 0, cell_widget)
            self.video_table.setItem(row_position, 1, QTableWidgetItem(f.get('format_id', '')))
            self.video_table.setItem(row_position, 2, QTableWidgetItem(f.get('ext', '')))
            self.video_table.setItem(row_position, 3, QTableWidgetItem(f.get('resolution', '')))
            self.video_table.setItem(row_position, 4, QTableWidgetItem(str(f.get('fps', ''))))
            self.video_table.setItem(row_position, 5, QTableWidgetItem(f.get('vcodec', '').split('.')[0]))
            self.video_table.setItem(row_position, 6, QTableWidgetItem(f"{filesize_mb:.2f}"))

    def populate_audio_table(self, formats):
        self.audio_table.setRowCount(0)
        audio_formats = sorted(
            [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none'],
            key=lambda x: x.get('abr', 0), reverse=True
        )
        for f in audio_formats:
            row_position = self.audio_table.rowCount()
            self.audio_table.insertRow(row_position)

            radio_button = QRadioButton()
            cell_widget = QWidget()
            layout = QHBoxLayout(cell_widget)
            layout.addWidget(radio_button)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0,0,0,0)
            
            filesize_mb = (f.get('filesize') or f.get('filesize_approx') or 0) / (1024 * 1024)

            self.audio_table.setCellWidget(row_position, 0, cell_widget)
            self.audio_table.setItem(row_position, 1, QTableWidgetItem(f.get('format_id', '')))
            self.audio_table.setItem(row_position, 2, QTableWidgetItem(f.get('ext', '')))
            self.audio_table.setItem(row_position, 3, QTableWidgetItem(str(f.get('abr', ''))))
            self.audio_table.setItem(row_position, 4, QTableWidgetItem(f.get('acodec', '').split('.')[0]))
            self.audio_table.setItem(row_position, 5, QTableWidgetItem(f"{filesize_mb:.2f}"))

    def populate_subtitle_list(self, subtitles, auto_subtitles):
        self.subtitle_list.clear()
        
        for lang, subs in subtitles.items():
            item = QListWidgetItem(f"{lang} ({self.tr('人工字幕')})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.subtitle_list.addItem(item)
            
        for lang, subs in auto_subtitles.items():
            item = QListWidgetItem(f"{lang} ({self.tr('自动生成')})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.subtitle_list.addItem(item)
    
    @Slot(QPixmap)
    def set_thumbnail(self, pixmap):
        self.thumbnail_label.setPixmap(pixmap.scaled(320, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    @Slot()
    def start_download(self):
        output_path = self.output_path_input.text()
        if not output_path or not os.path.isdir(output_path):
            QMessageBox.warning(self, self.tr("路径错误"), self.tr("请选择一个有效的保存文件夹。"))
            return

        ffmpeg_path = self.settings.value("ffmpeg_path", "")
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            QMessageBox.warning(self, self.tr("FFmpeg 未找到"), self.tr("请在设置中指定有效的 FFmpeg 路径，合并音视频需要它。"))
            return

        video_id = self.get_selected_track_id(self.video_table)
        audio_id = self.get_selected_track_id(self.audio_table)
        
        if not video_id or not audio_id:
            QMessageBox.warning(self, self.tr("选择不完整"), self.tr("请同时选择一个视频轨道和一个音频轨道进行下载和合并。"))
            return
            
        selected_format = f"{video_id}+{audio_id}"
        
        selected_subs = []
        for i in range(self.subtitle_list.count()):
            item = self.subtitle_list.item(i)
            if item.checkState() == Qt.Checked:
                lang_code = item.text().split(' ')[0]
                selected_subs.append(lang_code)

        ydl_opts = {
            'format': selected_format,
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': ffmpeg_path,
            'merge_output_format': 'mp4',
            'progress_hooks': [self.on_progress],
            'writethumbnail': True
        }

        if self.keep_files_checkbox.isChecked():
            ydl_opts['keepvideo'] = True
            
        if selected_subs:
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            ydl_opts['subtitleslangs'] = list(set(selected_subs))
        
        cookie_path = self.settings.value("cookie_path", "")
        if cookie_path and os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path

        self.set_ui_enabled(False)
        self.status_bar.showMessage(self.tr("开始下载..."))

        self.worker = DownloadWorker(self.url_input.text(), ydl_opts)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def get_selected_track_id(self, table):
        for i in range(table.rowCount()):
            cell_widget = table.cellWidget(i, 0)
            radio_button = cell_widget.layout().itemAt(0).widget()
            if radio_button.isChecked():
                return table.item(i, 1).text()
        return None

    def on_progress(self, d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                downloaded_bytes = d.get('downloaded_bytes', 0)
                percent = (downloaded_bytes / total_bytes) * 100
                self.progress_bar.setValue(int(percent))
                speed = d.get('_speed_str', 'N/A')
                self.status_bar.showMessage(f"{self.tr('下载中...')} {percent:.1f}%  {self.tr('速度')}: {speed}")
        elif d['status'] == 'finished':
            self.status_bar.showMessage(self.tr("下载完成，正在处理（如合并）..."))
            self.progress_bar.setValue(100)
        elif d['status'] == 'error':
             self.on_worker_error(self.tr("下载过程中发生错误。"))
             
    @Slot()
    def on_download_finished(self):
        message = self.tr("下载成功完成！")
        self.set_ui_enabled(True)
        self.status_bar.showMessage(message)
        QMessageBox.information(self, self.tr("完成"), message)

    @Slot(str)
    def on_worker_error(self, error_message):
        self.set_ui_enabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(f"{self.tr('错误')}: {error_message}")
        QMessageBox.critical(self, self.tr("发生错误"), error_message)

    def set_ui_enabled(self, enabled):
        self.url_input.setEnabled(enabled)
        self.fetch_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.tabs.setEnabled(enabled)
        self.keep_files_checkbox.setEnabled(enabled)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()

# --- 设置对话框 / Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("MyCompany", "YtDlpGUI")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        ffmpeg_layout = QHBoxLayout()
        self.ffmpeg_path_input = QLineEdit(self.settings.value("ffmpeg_path", ""))
        self.ffmpeg_browse_button = QPushButton()
        self.ffmpeg_browse_button.clicked.connect(self.browse_ffmpeg)
        self.ffmpeg_label = QLabel()
        ffmpeg_layout.addWidget(self.ffmpeg_label)
        ffmpeg_layout.addWidget(self.ffmpeg_path_input)
        ffmpeg_layout.addWidget(self.ffmpeg_browse_button)
        layout.addLayout(ffmpeg_layout)
        
        cookie_layout = QHBoxLayout()
        self.cookie_path_input = QLineEdit(self.settings.value("cookie_path", ""))
        self.cookie_browse_button = QPushButton()
        self.cookie_browse_button.clicked.connect(self.browse_cookie)
        self.cookie_label = QLabel()
        cookie_layout.addWidget(self.cookie_label)
        cookie_layout.addWidget(self.cookie_path_input)
        cookie_layout.addWidget(self.cookie_browse_button)
        layout.addLayout(cookie_layout)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.retranslate_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self):
        self.setWindowTitle(self.tr("设置"))
        self.ffmpeg_label.setText(self.tr("FFmpeg 路径:"))
        self.cookie_label.setText(self.tr("Cookie 文件路径:"))
        self.ffmpeg_browse_button.setText(self.tr("浏览..."))
        self.cookie_browse_button.setText(self.tr("浏览..."))
        self.save_button.setText(self.tr("保存"))
        self.cancel_button.setText(self.tr("取消"))
        
    def browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("选择 FFmpeg 可执行文件"), filter="All Files (*)")
        if path:
            self.ffmpeg_path_input.setText(path)

    def browse_cookie(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("选择 cookies.txt 文件"), filter="Text Files (*.txt);;All Files (*)")
        if path:
            self.cookie_path_input.setText(path)

    def save_settings(self):
        self.settings.setValue("ffmpeg_path", self.ffmpeg_path_input.text())
        self.settings.setValue("cookie_path", self.cookie_path_input.text())
        self.accept()

# --- 工作线程 / Worker Threads ---
class InfoWorker(QThread):
    info_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, url, cookie_path):
        super().__init__()
        self.url = url
        self.cookie_path = cookie_path

    def run(self):
        ydl_opts = {
            'quiet': True, 
            'skip_download': True,
            'writeautomaticsub': True
        }
        if self.cookie_path and os.path.exists(self.cookie_path):
            ydl_opts['cookiefile'] = self.cookie_path
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.info_ready.emit(info)
        except Exception as e:
            self.error.emit(str(e))

class ThumbnailWorker(QThread):
    image_ready = Signal(QPixmap)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            self.image_ready.emit(pixmap)
        except Exception as e:
            print(f"无法加载封面: {e}")

class DownloadWorker(QThread):
    finished_signal = Signal()
    error = Signal(str)
    
    def __init__(self, url, ydl_opts, parent=None):
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(str(e))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    settings = QSettings("MyCompany", "YtDlpGUI")
    locale = settings.value("language", QLocale.system().name())
    
    if translator.load(os.path.join(resolve_path("translations"), f"app_{locale}.qm")):
        app.installTranslator(translator)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
