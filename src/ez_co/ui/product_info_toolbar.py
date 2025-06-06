import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QSizePolicy, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QFont
from ez_co.utils.language_manager import get_text, get_log_text
from ez_co.handlers.virtual_path_handler import VirtualPathHandler

logger = logging.getLogger(__name__)

class ProductInfoToolbar(QWidget):
    """商品情報ツールバー"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_folder = None
        self.current_info_data = None
        
        # 自動更新用タイマー
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.auto_refresh)
        self.auto_refresh_timer.start(5000)  # 5秒ごとに更新
        
        self.setup_ui()
        self.show_no_info()
        
    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.product_info"))
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        # フォーカスポリシーを設定（フォーカスを奪わないように）
        self.setFocusPolicy(Qt.NoFocus)
        
        # メインウィジェットの背景色を明示的に設定
        self.setStyleSheet("""
            ProductInfoToolbar {
                background-color: transparent;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # タイトル
        title_label = QLabel(get_text("ui.product_info"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 14px; 
            padding: 5px;
            color: #ffffff;
            background-color: transparent;
        """)
        layout.addWidget(title_label)
        
        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #666666;")
        layout.addWidget(line)
        
        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }
            QScrollBar:vertical {
                background-color: #333333;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777777;
            }
        """)
        
        # メインコンテンツウィジェット
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(10)
        self.scroll_area.setWidget(self.content_widget)
        
        layout.addWidget(self.scroll_area)
        
        # サイズポリシーを設定
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
    def auto_refresh(self):
        """自動更新"""
        if self.current_folder:
            self.update_info(self.current_folder)
    
    def show_no_info(self):
        """商品情報がない旨を表示"""
        # 確実にクリアしてスクロールをトップに戻す
        self.clear_content()
        
        no_info_label = QLabel(get_text("ui.no_product_info_available"))
        no_info_label.setAlignment(Qt.AlignCenter)
        no_info_label.setWordWrap(True)
        no_info_label.setStyleSheet("""
            font-size: 12px; 
            color: #999999; 
            padding: 20px 10px; 
            border: 1px dashed #666666; 
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.05);
        """)
        self.content_layout.addWidget(no_info_label)
        self.content_layout.addStretch()
        
        logger.info(get_log_text("product_info_toolbar_no_info_displayed"))
        
    def clear_content(self):
        """コンテンツをクリア"""
        # スクロール位置をトップにリセット
        self.scroll_area.verticalScrollBar().setValue(0)
        
        # すべての子ウィジェットを削除
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child:
                if child.widget():
                    widget = child.widget()
                    widget.hide()  # 先に非表示にする
                    widget.setParent(None)
                    widget.deleteLater()
                elif child.layout():
                    layout = child.layout()
                    self._clear_layout(layout)
                    
        # レイアウトを強制的にリフレッシュ
        self.content_widget.update()
        
        # 遅延実行で確実にウィジェットを削除
        QTimer.singleShot(10, lambda: self.content_widget.update())
        
    def _clear_layout(self, layout):
        """レイアウトを再帰的にクリア"""
        while layout.count():
            child = layout.takeAt(0)
            if child:
                if child.widget():
                    widget = child.widget()
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
                elif child.layout():
                    self._clear_layout(child.layout())
    
    def update_info(self, folder_path: str):
        """指定フォルダの商品情報を更新"""
        try:
            logger.info(get_log_text("debug_product_info_toolbar_update_info_called", folder_path=folder_path))
            
            # 同じフォルダでも定期的に更新するため、スキップ処理を削除
            # これにより、ファイルが変更された時も確実に更新される
            if VirtualPathHandler.is_virtual_path(folder_path):
                folder_path = VirtualPathHandler.get_archive_parent_dir(folder_path)

            self.current_folder = folder_path
            info_json_path = Path(folder_path) / "info.json"
            logger.info(get_log_text("debug_product_info_toolbar_info_json_path", info_json_path=info_json_path))
            logger.info(get_log_text("debug_product_info_toolbar_info_json_exists", exists=info_json_path.exists()))
            
            if not info_json_path.exists():
                self.current_info_data = None
                self.show_no_info()
                # logger.info(get_log_text("product_info_toolbar_no_json", folder_path=folder_path))
                return
                
            logger.info(get_log_text("debug_product_info_toolbar_loading_json", info_json_path=info_json_path))
            with open(info_json_path, 'r', encoding='utf-8') as f:
                info_data = json.load(f)
            
            logger.info(get_log_text("debug_product_info_toolbar_json_loaded", data_keys=list(info_data.keys())))
            self.current_info_data = info_data
            self.display_info(info_data, folder_path)
            logger.info(get_log_text("product_info_toolbar_info_loaded", folder_path=folder_path))
            
        except Exception as e:
            logger.error(get_log_text("product_info_toolbar_load_error", error=e))
            self.show_error(get_text("ui.product_info_load_failed", error=str(e)))
            import traceback
            traceback.print_exc()
    
    def display_info(self, info_data: Dict[str, Any], folder_path: str):
        """商品情報を表示"""
        # 確実にクリアしてスクロールをトップに戻す
        self.clear_content()
        
        # タイトル
        title = info_data.get("タイトル", get_text("ui.product_title_unknown"))
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            font-size: 13px; 
            font-weight: bold; 
            margin-bottom: 8px; 
            color: #ffffff;
            background-color: transparent;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(title_label)
        
        # カテゴリー表示
        self.add_category_section(info_data)
        
        # URL情報（カテゴリー表示の後に配置）
        if "URL" in info_data:
            self.add_url_section(info_data["URL"])
        
        # 画像表示
        self.add_image_section(folder_path)
        
        # 基本情報
        self.add_basic_info_section(info_data)
        
        # ジャンル
        if "genre一覧" in info_data:
            self.add_genre_section(info_data["genre一覧"])
        
        # 概要（短縮版）
        if "概要" in info_data:
            self.add_overview_section(info_data["概要"])
        
        self.content_layout.addStretch()
    
    def add_category_section(self, info_data: Dict[str, Any]):
        """カテゴリーセクションを追加"""
        category_layout = QHBoxLayout()
        category_layout.setSpacing(3)
        
        # DLSite版かDMM版かを判定
        is_dmm = info_data.get("作品種別") == "DMM"
        
        if not is_dmm:
            # 年齢種別
            age_rating = info_data.get("年齢種別", "")
            if age_rating:
                age_label = self.create_category_label(age_rating, self.get_age_rating_style(age_rating))
                category_layout.addWidget(age_label)
                
            # カテゴリー
            category = info_data.get("カテゴリー", "")
            if category:
                category_label = self.create_category_label(category, self.get_category_style(category))
                category_layout.addWidget(category_label)
        
        # 作品種別
        work_type = info_data.get("作品種別", "")
        if work_type:
            work_type_label = self.create_category_label(work_type, self.get_work_type_style(work_type))
            category_layout.addWidget(work_type_label)
        
        category_layout.addStretch()
        
        if category_layout.count() > 1:  # stretchだけでない場合
            self.content_layout.addLayout(category_layout)
    
    def add_image_section(self, folder_path: str):
        """画像セクションを追加"""
        folder_jpg_path = Path(folder_path) / "folder.jpg"
        if folder_jpg_path.exists():
            try:
                pixmap = QPixmap(str(folder_jpg_path))
                if not pixmap.isNull():
                    # サイドバー用に適切なサイズにスケール
                    scaled_pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    image_label.setStyleSheet("""
                        border: 1px solid #666; 
                        margin: 5px 0; 
                        padding: 5px;
                        background-color: rgba(255, 255, 255, 0.05);
                        border-radius: 3px;
                    """)
                    self.content_layout.addWidget(image_label)
            except Exception as e:
                logger.error(get_log_text("product_info_toolbar_image_load_error", error=e))
    
    def add_basic_info_section(self, info_data: Dict[str, Any]):
        """基本情報セクションを追加"""
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(3)
        
        # 基本情報項目
        info_items = [
            ("PID", "ui.pid_label"),
            ("ブランド名", "ui.brand_name"),
            ("ファイル形式", "ui.file_format"),
            ("作品形式", "ui.work_format")
        ]
        
        for key, label_key in info_items:
            if key in info_data:
                value = info_data[key]
                if isinstance(value, list):
                    value = ", ".join(value)
                
                # ラベルと値を一行で表示
                info_text = f"{get_text(label_key)}: {value}"
                info_label = QLabel(info_text)
                info_label.setWordWrap(True)
                info_label.setStyleSheet("""
                    font-size: 11px; 
                    color: #cccccc; 
                    margin: 1px 0;
                    background-color: transparent;
                """)
                info_layout.addWidget(info_label)
        
        if info_layout.count() > 0:
            self.content_layout.addWidget(info_frame)
    
    def add_genre_section(self, genre_text: str):
        """ジャンルセクションを追加"""
        # ジャンルを分割
        genres = [genre.strip() for genre in genre_text.split(',') if genre.strip()]
        
        if not genres:
            return
        
        # ジャンルラベル
        genre_title = QLabel(get_text("ui.genre_label") + ":")
        genre_title.setStyleSheet("""
            font-size: 11px; 
            font-weight: bold; 
            color: #ffffff; 
            margin: 5px 0 2px 0;
            background-color: transparent;
        """)
        self.content_layout.addWidget(genre_title)
        
        # ジャンル表示（複数行対応）
        genre_container = QWidget()
        genre_container.setStyleSheet("background-color: transparent;")
        genre_layout = QVBoxLayout(genre_container)
        genre_layout.setContentsMargins(0, 0, 0, 0)
        genre_layout.setSpacing(2)
        
        # 3個ずつ表示
        for i in range(0, len(genres), 3):
            row_genres = genres[i:i+3]
            row_layout = QHBoxLayout()
            row_layout.setSpacing(2)
            
            for genre in row_genres:
                genre_label = self.create_category_label(genre, "background-color: #404040; color: #ddd;")
                genre_label.setStyleSheet(genre_label.styleSheet() + " font-size: 9px; padding: 2px 4px;")
                row_layout.addWidget(genre_label)
            
            row_layout.addStretch()
            genre_layout.addLayout(row_layout)
        
        self.content_layout.addWidget(genre_container)
    
    def add_overview_section(self, overview_text: str):
        """概要セクション（短縮版）を追加"""
        overview_title = QLabel(get_text("ui.overview_label") + ":")
        overview_title.setStyleSheet("""
            font-size: 11px; 
            font-weight: bold; 
            color: #ffffff; 
            margin: 5px 0 2px 0;
            background-color: transparent;
        """)
        self.content_layout.addWidget(overview_title)
        
        # 概要を短縮
        cleaned_text = self.clean_overview_text(overview_text)
        if len(cleaned_text) > 200:
            cleaned_text = cleaned_text[:200] + "..."
        
        overview_label = QLabel(cleaned_text)
        overview_label.setWordWrap(True)
        overview_label.setStyleSheet("""
            font-size: 10px; 
            color: #cccccc; 
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid #444444;
            border-radius: 3px;
            padding: 5px;
            margin: 2px 0;
        """)
        self.content_layout.addWidget(overview_label)
    
    def add_url_section(self, url: str):
        """URLセクションを追加"""
        url_button = QPushButton(get_text("ui.open_product_page_button"))
        url_button.setFocusPolicy(Qt.NoFocus)
        url_button.clicked.connect(lambda: self.open_url(url))
        url_button.setStyleSheet("""
            QPushButton { 
                background-color: #4CAF50; 
                color: white; 
                padding: 6px; 
                border-radius: 3px; 
                font-size: 10px;
                margin: 5px 0;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.content_layout.addWidget(url_button)
    
    def clean_overview_text(self, text: str) -> str:
        """概要テキストから複数改行を1行に変換"""
        import re
        # 2つ以上連続する改行を1つの改行に置換
        cleaned_text = re.sub(r'\n{2,}', '\n', text)
        return cleaned_text
    
    def create_category_label(self, text: str, style: str) -> QLabel:
        """カテゴリーラベルを作成"""
        label = QLabel(text)
        label.setStyleSheet(f"padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; {style}")
        label.setAlignment(Qt.AlignCenter)
        label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        return label
    
    def get_age_rating_style(self, age_rating: str) -> str:
        """年齢種別のスタイルを取得"""
        styles = {
            "R18": "background-color: #d32f2f; color: white;",
            "R-15": "background-color: #388e3c; color: white;", 
            "全年齢": "background-color: #1976d2; color: white;"
        }
        return styles.get(age_rating, "background-color: #757575; color: white;")
    
    def get_category_style(self, category: str) -> str:
        """カテゴリーのスタイルを取得"""
        styles = {
            "maniax": "background-color: #e91e63; color: white;",
            "books": "background-color: #ff9800; color: white;",
            "home": "background-color: #2196f3; color: white;",
            "pro": "background-color: #9c27b0; color: white;"
        }
        return styles.get(category, "background-color: #757575; color: white;")
    
    def get_work_type_style(self, work_type: str) -> str:
        """作品種別のスタイルを取得"""
        styles = {
            "ゲーム": "background-color: #f44336; color: white;",
            "マンガ": "background-color: #ff9800; color: white;",
            "CG・イラスト": "background-color: #4caf50; color: white;",
            "ノベル": "background-color: #2196f3; color: white;",
            "動画": "background-color: #9c27b0; color: white;",
            "ボイス・ASMR": "background-color: #e91e63; color: white;",
            "音楽": "background-color: #ff5722; color: white;",
            "ツール/アクセサリ": "background-color: #607d8b; color: white;",
            "DMM": "background-color: #ff6f00; color: white;",
            "その他": "background-color: #757575; color: white;"
        }
        return styles.get(work_type, "background-color: #757575; color: white;")
    
    def show_error(self, message: str):
        """エラーメッセージを表示"""
        # 確実にクリアしてスクロールをトップに戻す
        self.clear_content()
        
        error_label = QLabel(message)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setWordWrap(True)
        error_label.setStyleSheet("""
            font-size: 11px; 
            color: #d32f2f; 
            padding: 10px;
            background-color: transparent;
        """)
        self.content_layout.addWidget(error_label)
        self.content_layout.addStretch()
    
    def open_url(self, url: str):
        """URLを開く"""
        try:
            QDesktopServices.openUrl(QUrl(url))
            logger.info(get_log_text("product_info_toolbar_url_opened", url=url))
        except Exception as e:
            logger.error(get_log_text("product_info_toolbar_url_open_error", error=e)) 