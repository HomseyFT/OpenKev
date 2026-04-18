import sys
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QMainWindow,QPushButton, QTextEdit, QHBoxLayout, QVBoxLayout, QWidget, QLineEdit
from PySide6.QtGui import QColor, QPalette
from apps.KevAI.message import MessageWidget
from apps.KevAI.chatbar import ChatBar
from apps.KevAI.chatwindow import ChatWindow
# from ollama import generate
# Subclass QMainWindow to customize your application's main window

class Color(QWidget):
    def __init__(self, color):
        super().__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color))
        self.setPalette(palette)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kev-Ai")

        button = QPushButton("Press Me!")
        text1 = QTextEdit("Testing here")
        
        #Main Outer Layout
        layout = QHBoxLayout()
        # layout.addWidget(Color('red'), stretch = 1)
        # layout.addWidget(Color('green'), stretch = 5)

        #Sidebar
        sidebar = QVBoxLayout()
        sidebar.addWidget(Color('red'), stretch = 1)
        sidebar.addWidget(Color('green'), stretch = 1)
        container1 = QWidget()
        container1.setLayout(sidebar)
        layout.addWidget(container1, stretch=1)

        #Main Content Layout
        main = QVBoxLayout()
        # main.addWidget(Color('blue'), stretch = 1)
        self.chatWindow = ChatWindow()
        # self.chatWindow.add_message(MessageWidget("Me", "Hello!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Kev", "Hey there!", "kev.png", is_self=True))
        # self.chatWindow.add_message(MessageWidget("Me", "Oh hell nah!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Me", "Hello!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Kev", "Hey there!", "kev.png", is_self=True))
        # self.chatWindow.add_message(MessageWidget("Me", "Oh hell nah!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Me", "Hello!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Kev", "Hey there!", "kev.png", is_self=True))
        # self.chatWindow.add_message(MessageWidget("Me", "Oh hell nah!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Me", "Hello!", "kev.png", is_self=False))
        # self.chatWindow.add_message(MessageWidget("Kev", "Hey there!", "kev.png", is_self=True))
        # self.chatWindow.add_message(MessageWidget("Me", "Oh hell nah!", "kev.png", is_self=False))
        main.addWidget(self.chatWindow)
        main.addWidget(ChatBar(self.chatWindow))
        container2 = QWidget()
        container2.setLayout(main)
        layout.addWidget(container2, stretch = 5)
        
        # layout.addWidget(Color('blue'))

        # Create a container widget and set the layout on it
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)


# Regular appresponse
# response = generate('llama3.2:1b', 'Why is the sky blue?')
# print(response['response'])

if __name__ == "__main__":
    app = QApplication([])

    window = MainWindow()
    window.show()

    app.exec()