import sys
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QTextEdit, QLabel, QVBoxLayout,
                             QWidget, QHBoxLayout, QLineEdit, QStackedWidget)
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QTextBlockFormat, QKeyEvent
from PyQt6.QtCore import Qt, QEvent
import re
from utils import filter_english_and_punctuation
from llm import OllamaLLM, LanguageProcessor
import os
from tqdm import tqdm
import json


FIRST_PAGE = 15
LAST_PAGE = 306
FILE_PATH = "THE COMING WAVE.pdf"
PROCESSED_TEXT_PATH = "processed_texts.json"
BUTTON_HEIGHT = 35
TEXT_DISPLAY_WIDTH = 900

ENGLISH_FONT = QFont("Georgia")
ENGLISH_FONT.setPointSize(14)
ENGLISH_FORMAT = QTextCharFormat()
ENGLISH_FORMAT.setFont(ENGLISH_FONT)

CHINESE_FONT = QFont("SimHei")
CHINESE_FONT.setPointSize(15)
CHINESE_FORMAT = QTextCharFormat()
CHINESE_FORMAT.setFont(CHINESE_FONT)

SUMMARY_FONT = QFont("SimHei")
SUMMARY_FONT.setPointSize(12)
SUMMARY_FORMAT = QTextCharFormat()
SUMMARY_FORMAT.setFont(SUMMARY_FONT)
RESPONSE_LENGTH = 200


def is_valid_string(s):
    # 定义正则表达式，只允许英文字符、数字和标点符号
    pattern = r'[a-zA-Z0-9.,!?;:(){}\[\]\'\"\-— ’]+'

    # 使用 re.fullmatch 检查整个字符串
    return bool(re.fullmatch(pattern, s))


def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


class DocumentText:
    def __init__(self):
        self.paragraphs = [[] for _ in range(LAST_PAGE + 1)]
        self.translated_paragraphs = [[] for _ in range(LAST_PAGE + 1)]
        self.page_summary_100 = ["" for _ in range(LAST_PAGE + 1)]
        self.page_summary_200 = ["" for _ in range(LAST_PAGE + 1)]
        self.page_summary_300 = ["" for _ in range(LAST_PAGE + 1)]
        if os.path.exists(PROCESSED_TEXT_PATH):
            self.load()
        else:
            self.setup()

    def is_empty_page(self, page_index):
        return len(self.paragraphs[page_index]) == 0

    def setup(self):
        pdf_document = fitz.open(FILE_PATH)
        paragraph = ""
        for page_index in range(FIRST_PAGE, LAST_PAGE + 1):
            page = pdf_document.load_page(page_index)
            # 获取文本和其他元素
            blocks = page.get_text("blocks")  # 提取文本内容
            block_index = 0
            for block in blocks:
                block_text = block[4].replace("\n", " ").strip(" ")
                if paragraph == "":
                    paragraph = block_text
                    block_index += 1
                else:
                    paragraph += " " + block_text

                if not paragraph.endswith("."):
                    continue

                self.paragraphs[page_index].append(paragraph)
                paragraph = ""

    def preprocess(self, language_unit):
        for page_index in tqdm(range(LAST_PAGE + 1)):
            for paragraph_english in self.paragraphs[page_index]:
                paragraph_chinese = language_unit.translate(paragraph_english)
                self.translated_paragraphs[page_index].append(paragraph_chinese)
            if len(self.paragraphs[page_index]) > 0:
                summary_100 = language_unit.summarize(self.paragraphs[page_index], 100)
                self.page_summary_100[page_index] = summary_100
                summary_200 = language_unit.summarize(self.paragraphs[page_index], 200)
                self.page_summary_200[page_index] = summary_200
                summary_300 = language_unit.summarize(self.paragraphs[page_index], 300)
                self.page_summary_300[page_index] = summary_300
                self.save()

    def save(self):
        data = {
            "English": self.paragraphs,
            "Chinese": self.translated_paragraphs,
            "100-word summary": self.page_summary_100,
            "200-word summary": self.page_summary_200,
            "300-word summary": self.page_summary_300,
        }
        save_json(data, PROCESSED_TEXT_PATH)

    def load(self):
        data = load_json(PROCESSED_TEXT_PATH)
        self.paragraphs = data["English"]
        self.translated_paragraphs = data["Chinese"]
        self.page_summary_100 = data["100-word summary"]
        self.page_summary_200 = data["200-word summary"]
        self.page_summary_300 = data["300-word summary"]


class PDFViewer(QMainWindow):
    def __init__(self, model_name):
        super().__init__()
        os.system(f"ollama pull {model_name}")
        llm = OllamaLLM(model_name=model_name)
        self.language_unit = LanguageProcessor(llm)

        self.setWindowTitle("The Coming Wave")
        self.setGeometry(50, 50, 1400, 900)

        self.english_line_width = 700
        self.chinese_line_width = 600
        self.chat_line_width = 500
        self.current_page = FIRST_PAGE
        self.document_text = DocumentText()

        self.summary_length = 300
        # 创建主布局
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        text_layout = QVBoxLayout()
        text_display_widget = QStackedWidget()

        tab_button_layout = QHBoxLayout()

        english_display_button = QPushButton("英文原文")
        english_display_button.setFixedHeight(BUTTON_HEIGHT)
        english_display_button.clicked.connect(lambda: text_display_widget.setCurrentIndex(0))
        tab_button_layout.addWidget(english_display_button)

        chinese_display_button = QPushButton("中文翻译")
        chinese_display_button.setFixedHeight(BUTTON_HEIGHT)
        chinese_display_button.clicked.connect(lambda: text_display_widget.setCurrentIndex(1))
        tab_button_layout.addWidget(chinese_display_button)

        compare_display_button = QPushButton("中英对照")
        compare_display_button.setFixedHeight(BUTTON_HEIGHT)
        compare_display_button.clicked.connect(lambda: text_display_widget.setCurrentIndex(2))
        tab_button_layout.addWidget(compare_display_button)

        # summary_display_button = QPushButton("中文总结")
        # summary_display_button.setFixedHeight(BUTTON_HEIGHT)
        # summary_display_button.clicked.connect(lambda: text_display_widget.setCurrentIndex(3))
        # tab_button_layout.addWidget(summary_display_button)

        # 将按钮添加到布局
        text_layout.addLayout(tab_button_layout)
        text_layout.addWidget(text_display_widget)

        # 英文窗口
        self.english_text_display = QTextEdit(self)
        self.english_text_display.setReadOnly(True)
        self.english_text_display.setFixedWidth(self.english_line_width)
        self.english_text_display.setFontPointSize(12)
        self.english_text_display.setMinimumWidth(TEXT_DISPLAY_WIDTH)
        text_display_widget.addWidget(self.english_text_display)

        # 中文窗口
        self.chinese_text_display = QTextEdit(self)
        self.chinese_text_display.setReadOnly(True)
        self.chinese_text_display.setFixedWidth(self.chinese_line_width)
        self.chinese_text_display.setFontPointSize(12)
        self.chinese_text_display.setMinimumWidth(TEXT_DISPLAY_WIDTH)
        text_display_widget.addWidget(self.chinese_text_display)

        # 中英对照窗口
        self.compare_text_display = QTextEdit(self)
        self.compare_text_display.setReadOnly(True)
        self.compare_text_display.setFixedWidth(self.chinese_line_width)
        self.compare_text_display.setFontPointSize(12)
        self.compare_text_display.setMinimumWidth(TEXT_DISPLAY_WIDTH)
        text_display_widget.addWidget(self.compare_text_display)

        # 中文总结
        summary_text_display_label = QLabel("  中文总结")
        summary_text_display_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        summary_text_display_label.setMinimumWidth(TEXT_DISPLAY_WIDTH)
        summary_text_display_label.setFixedHeight(30)
        text_layout.addWidget(summary_text_display_label)
        self.summary_text_display = QTextEdit(self)
        self.summary_text_display.setReadOnly(True)
        self.summary_text_display.setFixedWidth(self.chinese_line_width)
        self.summary_text_display.setFont(CHINESE_FONT)
        self.summary_text_display.setFontPointSize(10)
        self.summary_text_display.setMinimumWidth(TEXT_DISPLAY_WIDTH)
        self.summary_text_display.setFixedHeight(180)
        text_layout.addWidget(self.summary_text_display)

        # 创建按钮布局
        self.page_button_layout = QHBoxLayout()
        self.first_page_button = QPushButton("第一页", self)
        self.first_page_button.setFixedHeight(BUTTON_HEIGHT)
        self.first_page_button.clicked.connect(self.show_first_page)
        self.page_button_layout.addWidget(self.first_page_button)

        self.prev_button = QPushButton("上一页", self)
        self.prev_button.setFixedHeight(BUTTON_HEIGHT)
        self.prev_button.clicked.connect(self.show_prev_page)
        self.page_button_layout.addWidget(self.prev_button)

        self.page_number_label = QPushButton("", self)
        self.page_number_label.setFixedHeight(BUTTON_HEIGHT)
        self.page_button_layout.addWidget(self.page_number_label)

        self.next_button = QPushButton("下一页", self)
        self.next_button.setFixedHeight(BUTTON_HEIGHT)
        self.next_button.clicked.connect(self.show_next_page)
        self.page_button_layout.addWidget(self.next_button)

        self.last_page_button = QPushButton("最后一页", self)
        self.last_page_button.setFixedHeight(BUTTON_HEIGHT)
        self.last_page_button.clicked.connect(self.show_last_page)
        self.page_button_layout.addWidget(self.last_page_button)

        text_layout.addLayout(self.page_button_layout)

        # 聊天窗口
        chat_layout = QVBoxLayout()
        chat_display_title = QLabel("对话记录")
        chat_display_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        chat_display_title.setFixedHeight(35)
        chat_layout.addWidget(chat_display_title)
        self.chat_display = QTextEdit(self)
        self.chat_display.setReadOnly(True)
        self.chat_display.setFixedWidth(self.chat_line_width)
        self.chat_display.setFontPointSize(13)
        self.chat_display.setFixedHeight(580)
        chat_layout.addWidget(self.chat_display)
        chat_input_title = QLabel("输入")
        chat_input_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        chat_input_title.setFixedHeight(30)
        chat_layout.addWidget(chat_input_title)
        self.chat_input = QTextEdit(self)
        self.chat_input.setFixedWidth(self.chat_line_width)
        self.chat_input.setFixedHeight(180)
        self.chat_input.setFontPointSize(15)
        self.chat_input.setPlaceholderText("按回车(Enter)发送消息")
        self.chat_input.installEventFilter(self)
        # self.chat_input.setFontPointSize(13)
        # self.chat_input.setMinimumHeight(200)
        chat_layout.addWidget(self.chat_input)
        self.chat_input_button = QPushButton("点击此按钮/按回车(Enter)发送消息", self)
        self.chat_input_button.clicked.connect(self.chat)
        self.chat_input_button.setFixedHeight(BUTTON_HEIGHT)
        chat_layout.addWidget(self.chat_input_button)

        # 设置文本窗口布局
        self.layout.addLayout(text_layout)
        self.layout.setAlignment(text_layout, Qt.AlignmentFlag.AlignLeft)
        self.layout.addLayout(chat_layout)
        self.layout.setAlignment(chat_layout, Qt.AlignmentFlag.AlignLeft)

        self.show_page(self.current_page)
        # self.has_LLM_read_this_path = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and obj is self.chat_input:
            if event.key() == Qt.Key.Key_Return and self.chat_input.hasFocus():
                self.chat()
        return super().eventFilter(obj, event)

    def set_page_number_label(self):
        self.page_number_label.setText(f"原书第 {self.current_page + 1} 页")

    def chat(self):
        message = self.chat_input.toPlainText().strip()
        if message:
            self.chat_display.append(f'<span style="font-size: 16px;color: red;">你</span>: '
                                     f'<span style="font-size: 16px;color: black;">{message}</span>')
            reply = self.language_unit.chat(message, RESPONSE_LENGTH)
            self.chat_display.append(f'<span style="font-size: 16px;color: blue;">AI</span>: '
                                     f'<span style="font-size: 16px;color: black;">{reply}</span>')
            self.chat_input.clear()

    def show_page(self, page_index):
        self.set_page_number_label()
        english_paragraphs = self.document_text.paragraphs[page_index]
        chinese_paragraphs = self.document_text.translated_paragraphs[page_index]

        self.english_text_display.clear()
        english_cursor = QTextCursor(self.english_text_display.document())
        for block in english_paragraphs:
            english_cursor.movePosition(QTextCursor.MoveOperation.End)
            english_cursor.insertText(block, ENGLISH_FORMAT)
            self.english_text_display.append("\n")

        self.chinese_text_display.clear()
        chinese_cursor = QTextCursor(self.chinese_text_display.document())
        for block in chinese_paragraphs:
            chinese_cursor.movePosition(QTextCursor.MoveOperation.End)
            chinese_cursor.insertText(block, CHINESE_FORMAT)
            self.chinese_text_display.append("\n")

        self.compare_text_display.clear()
        compare_cursor = QTextCursor(self.compare_text_display.document())
        for english_block, chinese_block in zip(english_paragraphs, chinese_paragraphs):
            compare_cursor.movePosition(QTextCursor.MoveOperation.End)
            compare_cursor.insertText(english_block, ENGLISH_FORMAT)
            self.compare_text_display.append("\n")
            compare_cursor.movePosition(QTextCursor.MoveOperation.End)
            compare_cursor.insertText(chinese_block, CHINESE_FORMAT)
            self.compare_text_display.append(f'<span style="font-size: 17px;color: #00cc00;">{"=" * 69}</span>')

        summary_cursor = QTextCursor(self.summary_text_display.document())
        summary_cursor.movePosition(QTextCursor.MoveOperation.End)
        self.summary_text_display.clear()
        summary_cursor.insertText(self.document_text.page_summary_200[page_index], SUMMARY_FORMAT)

    def show_first_page(self):
        if self.current_page != FIRST_PAGE:
            self.current_page = FIRST_PAGE
            self.show_page(self.current_page)

    def show_prev_page(self):
        if self.current_page > FIRST_PAGE:
            self.current_page -= 1
            while self.document_text.is_empty_page(self.current_page) and self.current_page > FIRST_PAGE:
                self.current_page -= 1
            self.show_page(self.current_page)

    def show_next_page(self):
        if self.current_page < LAST_PAGE:
            self.current_page += 1
            while self.document_text.is_empty_page(self.current_page) and self.current_page < LAST_PAGE:
                self.current_page += 1
            self.show_page(self.current_page)

    def show_last_page(self):
        if self.current_page != LAST_PAGE:
            self.current_page = LAST_PAGE
            self.show_page(self.current_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFViewer(model_name="glm4:9b")
    viewer.show()
    sys.exit(app.exec())
    # llm = OllamaLLM(model_name="glm4:9b")
    # language_unit = LanguageProcessor(llm)
    # doc = DocumentText(language_unit)
    # doc.preprocess()
    # p = x.paragraphs[:10]
    # from IPython import embed
    # embed()