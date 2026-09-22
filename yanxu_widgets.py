"""Small shared desktop controls with stable geometry and safe plain text."""
from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QTextLayout, QTextOption
from PyQt5.QtWidgets import QAbstractButton, QSizePolicy, QTextEdit
from yanxu_v2_app import make_icon


class NavigationButton(QAbstractButton):
    def __init__(self, key, text, callback):
        super().__init__()
        self.key = key
        self.setText(text)
        self.setObjectName('Nav')
        self.setCheckable(True)
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(callback)
        self.setAccessibleName(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isChecked()
        if selected or self.underMouse() or self.hasFocus():
            painter.setBrush(QColor('#E5F0EA' if selected else '#EAF1ED'))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),8,8)
        ink = '#176B5B' if selected else '#3D4C44'
        # One fixed icon column + one fixed text column for all label lengths.
        left = max(12, (self.width()-136)//2)
        make_icon(self.key, ink, 20).paint(painter,QRect(left,(self.height()-20)//2,20,20))
        font = self.font()
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(ink))
        painter.drawText(QRect(left+32,0,self.width()-left-38,self.height()),Qt.AlignLeft|Qt.AlignVCenter,self.text())

    def sizeHint(self):
        return QSize(176,46)


class TaskTitleButton(QAbstractButton):
    """Two-line preview, no minimum-width dependency on user-entered content."""
    def __init__(self, text, callback, completed=False):
        super().__init__()
        self.setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.completed = completed
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(callback)

    def sizeHint(self):
        return QSize(120,self.fontMetrics().lineSpacing()*2+6)

    def minimumSizeHint(self):
        return QSize(0,self.sizeHint().height())

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setPen(QColor('#64736B' if self.completed else '#202D28'))
        painter.setFont(self.font())
        text=' '.join(self.text().split())
        layout=QTextLayout(text,self.font())
        option=QTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        first=layout.createLine()
        if first.isValid():first.setLineWidth(max(1,self.width()-4))
        cut=first.textLength() if first.isValid() else 0
        layout.endLayout()
        line1=text[:cut]
        line2=self.fontMetrics().elidedText(text[cut:],Qt.ElideRight,max(1,self.width()-4))
        painter.drawText(2,self.fontMetrics().ascent()+2,line1)
        if line2:painter.drawText(2,self.fontMetrics().ascent()+self.fontMetrics().lineSpacing()+2,line2)
        if self.hasFocus():
            painter.setPen(QColor('#176B5B'))
            painter.drawRect(self.rect().adjusted(0,0,-1,-1))


class PlainTitleEdit(QTextEdit):
    """Accept legacy multiline titles without truncation or HTML interpretation."""
    def __init__(self,text=''):
        super().__init__()
        self.setAcceptRichText(False)
        self.setPlainText(text)
        self.setFixedHeight(82)

    def text(self):return self.toPlainText()

    def setText(self,text):self.setPlainText(text)
