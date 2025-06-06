import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QWidget, QTextBrowser, QFrame, QGridLayout, QPushButton,
    QSizePolicy
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QFont, QDesktopServices
from ez_co.utils.language_manager import get_text

class ProductInfoDialog(QDialog):
    """商品情報を表示するモーダレスダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(get_text("ui.product_info_dialog_title"))
        self.resize(800, 600)
        
        self.current_folder = None
        self.setup_ui()
        
    def setup_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        
        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # メインコンテンツウィジェット
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        scroll_area.setWidget(self.content_widget)
        
        layout.addWidget(scroll_area)
        
        # 初期状態では情報なしを表示
        self.show_no_info()
        
    def show_no_info(self):
        """商品情報がない旨を表示"""
        self.clear_content()
        
        no_info_label = QLabel(get_text("ui.no_product_info_available"))
        no_info_label.setAlignment(Qt.AlignCenter)
        no_info_label.setStyleSheet("font-size: 16px; color: #ccc; background-color: #2a2a2a; padding: 50px; border-radius: 5px;")
        self.content_layout.addWidget(no_info_label)
        
    def clear_content(self):
        """コンテンツをクリア"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child and child.widget():
                widget = child.widget()
                widget.setParent(None)
                widget.deleteLater()
            elif child and child.layout():
                self.clear_layout(child.layout())
    
    def clear_layout(self, layout):
        """レイアウトを再帰的にクリア"""
        if not layout:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child and child.widget():
                widget = child.widget()
                widget.setParent(None)
                widget.deleteLater()
            elif child and child.layout():
                self.clear_layout(child.layout())
    
    def update_info(self, folder_path: str):
        """指定フォルダの商品情報を更新"""
        self.current_folder = folder_path
        info_json_path = Path(folder_path) / "info.json"
        
        if not info_json_path.exists():
            self.show_no_info()
            return
            
        try:
            with open(info_json_path, 'r', encoding='utf-8') as f:
                info_data = json.load(f)
            self.display_info(info_data, folder_path)
        except Exception as e:
            self.show_error(get_text("ui.product_info_load_failed", error=str(e)))
    
    def display_info(self, info_data: Dict[str, Any], folder_path: str):
        """商品情報を表示"""
        self.clear_content()
        
        # タイトル
        title_label = QLabel(info_data.get("タイトル", get_text("ui.product_title_unknown")))
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.content_layout.addWidget(title_label)
        
        # カテゴリー・年齢種別・作品種別を横並びで表示
        category_layout = QHBoxLayout()
        
        # DLSite版かDMM版かを判定
        is_dmm = info_data.get("作品種別") == "DMM"
        
        if not is_dmm:
            # DLSite版の場合
            age_rating = info_data.get("年齢種別", "")
            if age_rating:
                age_label = self.create_category_label(age_rating, self.get_age_rating_style(age_rating))
                category_layout.addWidget(age_label)
                
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
        self.content_layout.addLayout(category_layout)
        
        # メインコンテンツを左右に分割
        main_content_layout = QHBoxLayout()
        
        # 左側：画像
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        self.add_image_section_to_layout(folder_path, left_layout)
        left_widget.setFixedWidth(220)
        main_content_layout.addWidget(left_widget)
        
        # 右側：基本情報
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # 基本情報グリッド
        info_grid = QGridLayout()
        row = 0
        
        # PID
        if "PID" in info_data:
            info_grid.addWidget(QLabel(get_text("ui.pid_label") + ":"), row, 0)
            info_grid.addWidget(QLabel(info_data["PID"]), row, 1)
            row += 1
            
        # ブランド名
        if "ブランド名" in info_data:
            info_grid.addWidget(QLabel(get_text("ui.brand_name") + ":"), row, 0)
            info_grid.addWidget(QLabel(info_data["ブランド名"]), row, 1)
            row += 1
            
        # ファイル形式
        if "ファイル形式" in info_data:
            info_grid.addWidget(QLabel(get_text("ui.file_format") + ":"), row, 0)
            info_grid.addWidget(QLabel(info_data["ファイル形式"]), row, 1)
            row += 1
            
        # 作品形式
        if "作品形式" in info_data:
            info_grid.addWidget(QLabel(get_text("ui.work_format") + ":"), row, 0)
            if isinstance(info_data["作品形式"], list):
                formats_text = ", ".join(info_data["作品形式"])
            else:
                formats_text = str(info_data["作品形式"])
            info_grid.addWidget(QLabel(formats_text), row, 1)
            row += 1
        
        info_grid.setColumnStretch(1, 1)
        right_layout.addLayout(info_grid)
        
        # ジャンル一覧
        if "genre一覧" in info_data:
            right_layout.addWidget(QLabel(get_text("ui.genre_label") + ":"))
            self.add_genre_section(info_data["genre一覧"], right_layout)
        
        right_layout.addStretch()
        main_content_layout.addWidget(right_widget)
        
        self.content_layout.addLayout(main_content_layout)
        
        # 概要
        if "概要" in info_data:
            self.content_layout.addWidget(QLabel(get_text("ui.overview_label") + ":"))
            overview_browser = QTextBrowser()
            # 複数改行を1行に変換
            cleaned_overview = self.clean_overview_text(info_data["概要"])
            overview_browser.setPlainText(cleaned_overview)
            overview_browser.setMaximumHeight(200)
            overview_browser.anchorClicked.connect(self.on_link_clicked)
            self.content_layout.addWidget(overview_browser)
        
        # URL情報
        if "URL" in info_data:
            url_button = QPushButton(get_text("ui.open_product_page_button"))
            url_button.clicked.connect(lambda: self.open_url(info_data["URL"]))
            url_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px; }")
            self.content_layout.addWidget(url_button)
        
        self.content_layout.addStretch()
    
    def add_image_section(self, folder_path: str):
        """画像セクションを追加（旧版互換）"""
        self.add_image_section_to_layout(folder_path, self.content_layout)
    
    def add_image_section_to_layout(self, folder_path: str, layout):
        """画像セクションを指定レイアウトに追加"""
        folder_jpg_path = Path(folder_path) / "folder.jpg"
        if folder_jpg_path.exists():
            try:
                pixmap = QPixmap(str(folder_jpg_path))
                if not pixmap.isNull():
                    # 画像を適切なサイズにスケール
                    scaled_pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    image_label.setStyleSheet("border: 1px solid #ddd; margin: 10px 0;")
                    layout.addWidget(image_label)
            except Exception as e:
                print(f"{get_text('ui.image_load_failed')}: {e}")
    
    def add_genre_section(self, genre_text: str, layout):
        """ジャンルセクションを追加"""
        # ジャンルを分割
        genres = [genre.strip() for genre in genre_text.split(',') if genre.strip()]
        
        if not genres:
            return
        
        # ジャンル表示用のコンテナ
        genre_container = QFrame()
        genre_layout = QHBoxLayout(genre_container)
        genre_layout.setContentsMargins(0, 0, 0, 0)
        genre_layout.setSpacing(5)
        
        # 各ジャンルをラベルとして追加
        for genre in genres:
            genre_label = self.create_category_label(genre, "background-color: #404040; color: white;")
            genre_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            genre_layout.addWidget(genre_label)
        
        genre_layout.addStretch()
        
        # スクロールエリアに設定
        scroll_area = QScrollArea()
        scroll_area.setWidget(genre_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setMaximumHeight(40)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        layout.addWidget(scroll_area)
    
    def clean_overview_text(self, text: str) -> str:
        """概要テキストから複数改行を1行に変換"""
        import re
        # 2つ以上連続する改行を1つの改行に置換
        cleaned_text = re.sub(r'\n{2,}', '\n', text)
        return cleaned_text
    
    def create_category_label(self, text: str, style: str) -> QLabel:
        """カテゴリーラベルを作成"""
        label = QLabel(text)
        label.setStyleSheet(f"padding: 4px 8px; border-radius: 3px; font-weight: bold; {style}")
        label.setAlignment(Qt.AlignCenter)
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
        self.clear_content()
        
        error_label = QLabel(message)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("font-size: 14px; color: #d32f2f; padding: 20px;")
        self.content_layout.addWidget(error_label)
    
    def on_link_clicked(self, url: QUrl):
        """リンククリック時の処理"""
        QDesktopServices.openUrl(url)
    
    def open_url(self, url: str):
        """URLを開く"""
        QDesktopServices.openUrl(QUrl(url)) 