"""Local-first YanXu desktop. Cloud and mobile clients remain unchanged."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time

from PyQt5.QtCore import QDate, Qt, QTimer, QTime, QByteArray, QLockFile
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QScrollArea,
    QLineEdit, QCheckBox, QComboBox, QSpinBox, QDateEdit, QTimeEdit, QTextEdit,
    QDialog, QDialogButtonBox, QStackedWidget, QButtonGroup, QProgressBar,
    QFileDialog, QMessageBox, QCalendarWidget, QSystemTrayIcon, QMenu, QSizePolicy)

from yanxu_v2_app import YanXu, APP_DIR, make_icon, resource_path, clear_layout
from yanxu_store import LocalStore
from yanxu_widgets import NavigationButton, TaskTitleButton, PlainTitleEdit
from yanxu_insights import week_summary, week_report, starter_task, review_due, review_feedback

VERSION = '2.3.1-desktop-preview'
STATUS = {'pending':'待开始','in_progress':'进行中','waiting':'等待','blocked':'阻塞','completed':'已完成','cancelled':'已取消'}


def label(text, role='Body'):
    result = QLabel(text)
    result.setTextFormat(Qt.PlainText)
    result.setObjectName(role)
    result.setWordWrap(True)
    return result


def button(text, callback, primary=False):
    result = QPushButton(text)
    result.setObjectName('Primary' if primary else 'Secondary')
    result.clicked.connect(callback)
    return result


def scroll_content():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName('ListCanvas')
    box = QVBoxLayout(content)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(12)
    scroll.setWidget(content)
    return scroll, box


class TaskEditor(QDialog):
    def __init__(self, owner, row=None):
        super().__init__(owner)
        self.row = row or {}
        self.setWindowTitle('编辑任务' if row else '新建任务')
        self.resize(480, 410)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        scroll, layout = scroll_content()
        outer.addWidget(scroll,1)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.title = PlainTitleEdit(self.row.get('title', ''))
        self.title.setPlaceholderText('例如：整理本周实验结果')
        form.addRow('要做什么？', self.title)
        self.start = QDateEdit()
        self.end = QDateEdit()
        for widget, key in ((self.start, 'start_date'), (self.end, 'end_date')):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat('yyyy-MM-dd')
            value = QDate.fromString(self.row.get(key) or dt.date.today().isoformat(), 'yyyy-MM-dd')
            widget.setDate(value if value.isValid() else QDate.currentDate())
        form.addRow('开始日期', self.start)
        form.addRow('目标完成日', self.end)
        self.project = QComboBox()
        self.project.addItem('不关联项目', None)
        for project in owner.data.get('projects', []):
            self.project.addItem(project.get('name') or '未命名项目', project['id'])
        self.project.setCurrentIndex(max(0, self.project.findData(self.row.get('project_id'))))
        form.addRow('所属项目', self.project)
        self.priority = QCheckBox('列为今日重点')
        self.priority.setChecked(self.row.get('priority') in ('high', 'today'))
        form.addRow('', self.priority)
        layout.addLayout(form)
        expand = QPushButton('更多选项 · 时间、提醒、备注')
        expand.setCheckable(True)
        expand.setObjectName('Quiet')
        layout.addWidget(expand)
        self.extra = QWidget()
        more = QFormLayout(self.extra)
        more.setContentsMargins(0, 0, 0, 0)
        self.has_time = QCheckBox('指定开始时刻')
        self.has_time.setChecked(bool(self.row.get('start_time')))
        self.clock = QTimeEdit(QTime.fromString((self.row.get('start_time') or '09:00')[:5], 'HH:mm'))
        self.clock.setDisplayFormat('HH  mm')
        self.clock.setEnabled(self.has_time.isChecked())
        self.has_time.toggled.connect(self.clock.setEnabled)
        times = QHBoxLayout()
        times.addWidget(self.has_time)
        times.addWidget(self.clock)
        more.addRow('开始时间', times)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 1440)
        self.minutes.setSpecialValueText('未指定')
        self.minutes.setSuffix(' 分钟')
        self.minutes.setValue(self.row.get('estimated_minutes') or 0)
        more.addRow('预计用时', self.minutes)
        self.reminder = QComboBox()
        for title, value in [('不提醒', -1), ('准时提醒', 0), ('提前 10 分钟', 10), ('提前 30 分钟', 30)]:
            self.reminder.addItem(title, value)
        policy = self.row.get('reminder_policy') or {}
        lead = policy.get('minutes_before', 10) if policy.get('enabled', True) else -1
        index = self.reminder.findData(lead)
        if index < 0:
            self.reminder.addItem(f'提前 {lead} 分钟', lead)
            index = self.reminder.count() - 1
        self.reminder.setCurrentIndex(index if row else 0)
        more.addRow('任务提醒', self.reminder)
        self.status = QComboBox()
        for key, title in STATUS.items():
            self.status.addItem(title, key)
        self.status.setCurrentIndex(max(0, self.status.findData(self.row.get('status', 'pending'))))
        more.addRow('状态', self.status)
        self.notes = QTextEdit(self.row.get('description') or '')
        self.notes.setFixedHeight(76)
        more.addRow('备注', self.notes)
        layout.addWidget(self.extra)
        self.extra.hide()
        expand.toggled.connect(self.expand)
        self.error = label('', 'Muted')
        layout.addWidget(self.error)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        actions.button(QDialogButtonBox.Save).setText('保存任务')
        actions.button(QDialogButtonBox.Save).setObjectName('Primary')
        actions.button(QDialogButtonBox.Cancel).setText('取消')
        actions.accepted.connect(self.validate)
        actions.rejected.connect(self.reject)
        outer.addWidget(actions)
        outer.setContentsMargins(12,8,12,12)
        self.title.setFocus()

    def expand(self, expanded):
        self.extra.setVisible(expanded)
        available=QApplication.primaryScreen().availableGeometry().height()
        self.resize(500,min(720 if expanded else 410,available-80))

    def validate(self):
        if not self.title.text().strip():
            self.error.setText('请先填写任务名称。')
        elif self.end.date() < self.start.date():
            self.error.setText('目标完成日不能早于开始日期。')
        else:
            self.accept()

    def value(self):
        lead = self.reminder.currentData()
        policy = dict(self.row.get('reminder_policy') or {})
        policy.update(enabled=lead >= 0, minutes_before=max(0, lead))
        return {'title':self.title.text().strip(), 'start_date':self.start.date().toString('yyyy-MM-dd'),
                'end_date':self.end.date().toString('yyyy-MM-dd'), 'project_id':self.project.currentData(),
                'start_time':self.clock.time().toString('HH:mm') if self.has_time.isChecked() else None,
                'all_day':not self.has_time.isChecked(), 'priority':'today' if self.priority.isChecked() else 'normal',
                'status':self.status.currentData(), 'estimated_minutes':self.minutes.value() or None,
                'description':self.notes.toPlainText().strip(), 'reminder_policy':policy}


class DesktopWindow(YanXu):
    def __init__(self, directory=None):
        QMainWindow.__init__(self)
        self.directory = Path(directory or APP_DIR)
        self.store = LocalStore(self.directory)
        self.settings_path = self.directory / 'desktop-settings.json'
        self.settings = {'font_size':16, 'notifications_enabled':True, 'task_reminders':True, 'daily_summary':False, 'reminder_minutes':10}
        if self.settings_path.exists():
            self.settings.update(json.loads(self.settings_path.read_text(encoding='utf-8')))
        self.data = self.store.load()
        self.space_id = ''
        self.notified = set()
        self.tray = None
        self.active_key = 'today'
        self.undo_action = None
        self.focus_task = None
        self.focus_started = None
        self.focus_elapsed = 0.0
        self.setWindowTitle('研序 YanXu · 桌面版')
        self.setFont(QFont('Microsoft YaHei UI',11))
        self.setWindowIcon(QIcon(resource_path('assets/yanxu-logo-1024.png')))
        self.resize(1160, 760)
        self.setMinimumSize(840, 560)
        self.setStyleSheet(self.style())
        self.build()
        if self.settings.get('geometry'):
            self.restoreGeometry(QByteArray.fromHex(self.settings['geometry'].encode('ascii')))
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.resize(min(1160, int(screen.width()*.85)), min(760, int(screen.height()*.85)))
            self.center_window()
        self.setup_notifications()
        self.focus_timer = QTimer(self)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self.update_focus)
        self.focus_timer.start()
        self.show_page('today')

    def style(self):
        size = max(14, min(24, int(self.settings.get('font_size', 16))))
        row_pad = 2 if self.settings.get('compact_mode') else 6
        return f'''
        QWidget {{font-family:"Microsoft YaHei UI";font-size:{size}px;color:#202D28;background:#F6F8F7;}}
        QLabel {{background:transparent;}} QLabel#Muted {{color:#64736B;font-size:{max(13,size-2)}px;}}
        QLabel#Title {{font-size:{size+10}px;font-weight:600;}} QLabel#Section {{font-size:{size+1}px;font-weight:600;}}
        QLabel#Brand {{font-size:24px;font-weight:600;}} QFrame#Sidebar {{background:#F0F4F2;border-right:1px solid #DFE7E2;}}
        QPushButton {{min-height:34px;padding:3px 12px;border:1px solid #DFE7E2;border-radius:8px;background:white;}}
        QPushButton:hover {{background:#E5F0EA;}} QPushButton#Primary {{background:#176B5B;color:white;border-color:#176B5B;}}
        QPushButton:disabled {{color:#98A39D;background:#EFF3F0;border-color:#E4EAE6;}}
        QPushButton#Primary:hover {{background:#125648;}} QPushButton#Quiet {{border:0;background:transparent;text-align:left;}}
        QAbstractButton#Nav {{font-family:"Microsoft YaHei UI";font-size:{size+1}px;font-weight:400;background:transparent;}}
        QFrame#Card {{background:white;border:1px solid #DFE7E2;border-radius:10px;}}
        QWidget#ListCanvas {{background:white;}} QScrollArea#Aside QWidget#ListCanvas {{background:#F6F8F7;}}
        QFrame#Task {{background:white;border:0;border-bottom:1px solid #E8EEEA;padding:{row_pad}px 0;}}
        QFrame#Task:hover {{background:#F5F9F6;}} QFrame#Task QPushButton {{background:transparent;border:0;text-align:left;padding:0;}}
        QLineEdit,QComboBox,QSpinBox,QDateEdit,QTimeEdit,QTextEdit {{background:white;border:1px solid #DFE7E2;border-radius:7px;min-height:32px;padding:3px 8px;selection-background-color:#D4E8DF;}}
        QLineEdit:focus,QTextEdit:focus {{border-color:#176B5B;}} QCheckBox {{background:transparent;spacing:8px;}}
        QCheckBox::indicator {{width:20px;height:20px;}} QScrollArea {{border:0;background:transparent;}}
        QCheckBox#Done::indicator {{border:1px solid #9AAEA1;border-radius:10px;background:white;}}
        QCheckBox#Done::indicator:checked {{background:#176B5B;border:4px solid #C7E2D5;}}
        QScrollBar:vertical {{width:8px;background:transparent;}} QScrollBar::handle:vertical {{background:#CBD8D0;border-radius:4px;min-height:25px;}}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
        QTextEdit#Reading {{border:0;background:white;padding:8px;font-size:{size}px;}}
        QProgressBar {{border:0;border-radius:4px;background:#E8EEEA;max-height:8px;}}
        QProgressBar::chunk {{background:#5F9988;border-radius:4px;}}
        QToolTip {{background:white;color:#202D28;border:1px solid #DFE7E2;}}
        '''

    def build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName('Sidebar')
        self.sidebar.setFixedWidth(208)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14,24,14,18)
        side.setSpacing(4)
        side.addWidget(label('研序  YanXu', 'Brand'))
        side.addWidget(label('专注于下一步', 'Muted'))
        side.addSpacing(22)
        self.buttons = {}
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, title in [('today','今日'),('tasks','任务'),('projects','项目'),('calendar','日历'),('inbox','收集箱'),('reviews','知识卡片'),('weekly','成长记录'),('settings','设置')]:
            if key == 'settings': side.addStretch()
            b = NavigationButton(key,title,lambda _, k=key:self.show_page(k))
            side.addWidget(b)
            self.nav_group.addButton(b)
            self.buttons[key] = b
        side.addWidget(label('本地保存 · 无需登录', 'Muted'))
        layout.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages,1)
        self.content = QWidget()
        self.pages.addWidget(self.content)
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(26,22,26,16)
        self.body.setSpacing(16)
        self.detail = QDialog(self)
        self.detail.setWindowTitle('任务详情')
        self.detail.setWindowModality(Qt.WindowModal)
        self.detail_layout=QVBoxLayout(self.detail)
        self.detail_layout.setContentsMargins(24,20,24,20)
        self.detail_layout.setSpacing(14)
        self.detail.hide()

    def show_page(self, key):
        self.active_key = key
        self.content.setProperty('key',key)
        self.buttons[key].setChecked(True)
        self.detail.hide()
        self.render(key)

    def refresh(self):
        self.data = self.store.load()
        self.render(self.active_key)

    def set_sync_state(self, text, failed=False):
        if getattr(self,'feedback',None) is not None: self.feedback.setText(text)

    def upsert(self, table, value, row=None):
        try:
            self.store.upsert(table, value, row)
        except Exception as error:
            self.message('未能保存，请勿关闭窗口。\n'+str(error))
            return False
        self.refresh()
        self.set_sync_state('已保存到本机')
        return True

    def header(self, title, subtitle, action=None, callback=None):
        row = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(4)
        copy.addWidget(label(title,'Title'))
        copy.addWidget(label(subtitle,'Muted'))
        row.addLayout(copy,1)
        if action: row.addWidget(button(action,callback,True))
        self.body.addLayout(row)

    def render(self, key):
        self.feedback=None
        clear_layout(self.body)
        if key == 'settings': self.render_settings(); return
        if key == 'today': self.render_today()
        elif key in ('tasks','calendar'): self.render_tasks(key)
        elif key == 'reviews': self.render_knowledge()
        elif key == 'weekly': self.render_growth()
        else: self.render_collection(key)
        foot = QHBoxLayout()
        self.feedback = label('本地保存 · 今日备份已就绪','Muted')
        self.feedback.setWordWrap(False)
        self.feedback.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        foot.addWidget(self.feedback,1)
        if self.undo_action: foot.addWidget(button('撤销上次操作',self.undo))
        self.focus_label = label('','Muted')
        foot.addWidget(self.focus_label)
        self.focus_button = button('开始专注', self.toggle_focus)
        foot.addWidget(self.focus_button)
        if self.focus_task is not None: foot.addWidget(button('结束',self.finish_focus))
        self.body.addLayout(foot)
        self.update_focus()

    def task_row(self, task):
        frame = QFrame()
        frame.setObjectName('Task')
        row = QHBoxLayout(frame)
        row.setContentsMargins(10,4,10,4)
        done = QCheckBox()
        done.setObjectName('Done')
        done.setAccessibleName('完成 '+task.get('title','任务'))
        done.setChecked(task.get('status') == 'completed')
        done.clicked.connect(lambda checked:self.complete_task(task, checked))
        row.addWidget(done)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = TaskTitleButton(task.get('title') or '未命名任务',lambda:self.show_detail(task),task.get('status')=='completed')
        copy.addWidget(title)
        project = next((p.get('name','') for p in self.data['projects'] if p['id']==task.get('project_id')), '')
        parts = [part for part in [(task.get('start_time') or '')[:5],project] if part]
        if task.get('estimated_minutes'): parts.append(f"预计 {task['estimated_minutes']} 分钟")
        if task.get('end_date'): parts.append('截止 '+task['end_date'])
        copy.addWidget(label(' · '.join(parts) or '未安排时间','Muted'))
        row.addLayout(copy,1)
        if task.get('status') in ('completed','blocked','in_progress'): row.addWidget(label(STATUS[task['status']],'Muted'))
        return frame

    def render_today(self):
        today = dt.date.today().isoformat()
        self.header('今日',dt.date.today().strftime('%m 月 %d 日')+' · 把注意力留给值得推进的事。','＋ 新建任务',lambda:self.edit_task(None))
        grid = QHBoxLayout()
        grid.setSpacing(22)
        card = QFrame()
        card.setObjectName('Card')
        box = QVBoxLayout(card)
        box.setContentsMargins(18,16,18,12)
        scroll, listing = scroll_content()
        active = [t for t in self.data['tasks'] if (t.get('start_date') or today)<=today and t.get('status') not in ('completed','cancelled')]
        active.sort(key=lambda t:(t.get('end_date') or '9999',t.get('start_time') or '99'))
        groups = [('今日重点',[t for t in active if t.get('priority') in ('today','high')]),('其他安排',[t for t in active if t.get('priority') not in ('today','high')])]
        completed = [t for t in self.data['tasks'] if t.get('status')=='completed' and (t.get('completed_at') or '')[:10]==today]
        if not active:
            listing.addWidget(label('今天的安排已完成' if completed else '从一件小事开始','Section'))
            listing.addWidget(label('给已经做完的事情留一点肯定。' if completed else '不必排满一天，先确定下一步。','Muted'))
            listing.addWidget(button('＋ 添加任务',lambda:self.edit_task(None)),0,Qt.AlignLeft)
        else:
            for title, tasks in groups:
                if tasks:
                    listing.addWidget(label(f'{title} · {len(tasks)}','Section'))
                    for task in tasks: listing.addWidget(self.task_row(task))
        if completed:
            listing.addWidget(label(f'今日已完成 · {len(completed)}','Section'))
            for task in completed: listing.addWidget(self.task_row(task))
        listing.addStretch()
        box.addWidget(scroll)
        grid.addWidget(card,3)
        right_scroll, right = scroll_content()
        right_scroll.setObjectName('Aside')
        right_scroll.setMinimumWidth(180)
        right.addWidget(label('近期截止','Section'))
        upcoming = sorted([t for t in self.data['tasks'] if t.get('status') not in ('completed','cancelled') and t.get('end_date')],key=lambda t:t['end_date'])[:3]
        for task in upcoming:
            action=TaskTitleButton(task.get('title','任务'),lambda _, t=task:self.show_detail(t))
            right.addWidget(action)
            right.addWidget(label(('已逾期 · ' if task['end_date']<today else '截止 ') + task['end_date'],'Muted'))
        if not upcoming: right.addWidget(label('暂无截止事项','Muted'))
        right.addSpacing(18)
        right.addWidget(label('项目下一步','Section'))
        projects = [p for p in self.data['projects'] if p.get('status','active')=='active']
        for project in projects[:3]:
            right.addWidget(label(project.get('name','项目')))
            right.addWidget(label(project.get('next_action') or '尚未安排下一步','Muted'))
        if not projects: right.addWidget(label('创建项目，把长期目标拆成行动。','Muted'))
        right.addWidget(button('查看项目',lambda:self.show_page('projects')))
        right.addSpacing(16)
        right.addWidget(label('轻量起步','Section'))
        right.addWidget(label('不知道先做什么？从预计 15 分钟内能完成的任务开始。','Muted'))
        right.addWidget(button('挑一件小任务',self.suggest_starter))
        right.addStretch()
        grid.addWidget(right_scroll,1)
        self.body.addLayout(grid,1)

    def render_tasks(self,key):
        self.header('日历' if key=='calendar' else '任务','选择日期查看安排。' if key=='calendar' else '记录、安排、执行，然后完成。','＋ 新建任务',lambda:self.edit_task(None))
        if key=='calendar':
            calendar = QCalendarWidget()
            calendar.setMaximumHeight(230)
            calendar.setSelectedDate(getattr(self,'calendar_date',QDate.currentDate()))
            calendar.clicked.connect(self.select_date)
            self.body.addWidget(calendar)
        else:
            filters = QHBoxLayout()
            self.search = QLineEdit(getattr(self,'search_term',''))
            self.search.setPlaceholderText('搜索任务…')
            self.search.textChanged.connect(self.filter_tasks)
            filters.addWidget(self.search,1)
            self.status_filter = QComboBox()
            self.status_filter.addItems(['未完成','已完成','全部'])
            self.status_filter.setCurrentText(getattr(self,'filter_value','未完成'))
            self.status_filter.currentTextChanged.connect(self.filter_tasks)
            filters.addWidget(self.status_filter)
            self.body.addLayout(filters)
        scroll,self.task_listing = scroll_content()
        self.body.addWidget(scroll,1)
        self.fill_tasks()

    def select_date(self,date):
        self.calendar_date=date
        self.fill_tasks()

    def filter_tasks(self,_=None):
        self.search_term=self.search.text()
        self.filter_value=self.status_filter.currentText()
        self.fill_tasks()

    def fill_tasks(self):
        clear_layout(self.task_listing)
        rows = self.data['tasks']
        if self.active_key=='calendar':
            day=getattr(self,'calendar_date',QDate.currentDate()).toString('yyyy-MM-dd')
            rows=[t for t in rows if (t.get('start_date') or day)<=day<=(t.get('end_date') or day)]
        else:
            rows=[t for t in rows if getattr(self,'search_term','').casefold() in t.get('title','').casefold()]
            mode=getattr(self,'filter_value','未完成')
            if mode=='未完成': rows=[t for t in rows if t.get('status') not in ('completed','cancelled')]
            if mode=='已完成': rows=[t for t in rows if t.get('status')=='completed']
        for task in rows: self.task_listing.addWidget(self.task_row(task))
        if not rows: self.task_listing.addWidget(label('这里暂时没有任务。','Muted'))
        self.task_listing.addStretch()

    def show_detail(self, task):
        clear_layout(self.detail_layout)
        self.detail_layout.addWidget(label('任务详情','Section'))
        project=next((p.get('name','项目') for p in self.data['projects'] if p['id']==task.get('project_id')),'不关联项目')
        self.detail_layout.addWidget(label(STATUS.get(task.get('status'),'待开始')+' · '+project,'Muted'))
        self.detail_layout.addWidget(label('开始 '+str(task.get('start_date') or '未指定')+'   /   目标完成 '+str(task.get('end_date') or '未指定'),'Muted'))
        reader=QTextEdit()
        reader.setObjectName('Reading')
        reader.setReadOnly(True)
        reader.setAcceptRichText(False)
        reader.setPlainText((task.get('title') or '未命名任务')+('\n\n备注\n'+task['description'] if task.get('description') else ''))
        reader.moveCursor(reader.textCursor().Start)
        self.detail_layout.addWidget(reader,1)
        actions=QHBoxLayout()
        actions.addWidget(button('编辑',lambda:self.edit_task(task)))
        focus=button('开始专注',lambda:self.focus_from_detail(task))
        focus.setEnabled(task.get('status') not in ('completed','cancelled'))
        actions.addWidget(focus)
        actions.addStretch()
        actions.addWidget(button('恢复待完成' if task.get('status')=='completed' else '完成任务',lambda:self.complete_task(task,task.get('status')!='completed'),True))
        self.detail_layout.addLayout(actions)
        bottom=QHBoxLayout()
        bottom.addWidget(button('删除…',lambda:self.delete_task(task)))
        bottom.addStretch()
        bottom.addWidget(button('关闭',self.detail.close))
        self.detail_layout.addLayout(bottom)
        area=QApplication.primaryScreen().availableGeometry()
        self.detail.resize(min(660,area.width()-80),min(540,area.height()-80))
        self.detail.move(self.frameGeometry().center()-self.detail.rect().center())
        self.detail.show()

    def focus_from_detail(self,task):
        self.detail.hide()
        self.start_focus(task)

    def suggest_starter(self):
        task=starter_task(self.data['tasks'])
        if task:
            self.show_detail(task)
        else:
            QMessageBox.information(self,'轻量起步','目前没有预计 15 分钟内、已经可以开始的未完成任务。\n可以把大任务拆成一个小步骤，并在“更多选项”填写预计用时。')

    def edit_task(self,row=None):
        reopen=self.detail.isVisible()
        self.detail.hide()
        dialog=TaskEditor(self,row)
        if dialog.exec_()==QDialog.Accepted:
            value=dialog.value()
            if value['status']=='completed' and (row or {}).get('status')!='completed': value['completed_at']=dt.datetime.now().isoformat()
            if value['status']!='completed': value['completed_at']=None
            if self.upsert('tasks',value,row): self.detail.hide()
        elif reopen and row:self.show_detail(row)

    def complete_task(self,task,completed):
        self.undo_action=('tasks',dict(task))
        if self.upsert('tasks',{'status':'completed' if completed else 'pending','completed_at':dt.datetime.now().isoformat() if completed else None},task):
            self.detail.hide()
            self.set_sync_state('任务已完成 · 可撤销' if completed else '已恢复为待完成')

    def delete_task(self,task):
        if QMessageBox.question(self,'删除任务','删除“'+task.get('title','任务')+'”？删除后可撤销。')!=QMessageBox.Yes: return
        self.undo_action=('tasks',dict(task))
        if self.upsert('tasks',{'deleted_at':dt.datetime.now().isoformat()},task): self.detail.hide()

    def undo(self):
        if not self.undo_action:return
        kind,row=self.undo_action
        self.undo_action=None
        self.upsert(kind,row)

    def render_collection(self,key):
        titles={'projects':'项目','inbox':'收集箱','reviews':'复习','weekly':'回顾'}
        self.header(titles[key],{'projects':'长期目标，从明确的下一步开始。','inbox':'先记下来，稍后再安排。','reviews':'巩固值得长期记住的内容。','weekly':'记录推进、阻碍和下一步。'}[key],'＋ 新建',lambda:self.create(key))
        scroll,box=scroll_content()
        rows=self.data.get('weekly_reviews' if key=='weekly' else key,[])
        if key=='inbox':rows=[r for r in rows if r.get('status')!='converted']
        for row in rows:
            card=QFrame();card.setObjectName('Card');layout=QVBoxLayout(card)
            layout.setContentsMargins(20,18,20,18);layout.setSpacing(10)
            title=row.get('name') or row.get('title') or row.get('content') or row.get('highlights') or '未命名记录'
            layout.addWidget(label(title,'Section'))
            if key=='projects':
                layout.addWidget(label('目标','Muted'))
                goal=label(row.get('goal') or '尚未填写目标，可通过“编辑项目”补充。')
                goal.setTextInteractionFlags(Qt.TextSelectableByMouse)
                layout.addWidget(goal)
                layout.addWidget(label('下一步：'+(row.get('next_action') or '尚未设置'),'Muted'))
                related=[t for t in self.data['tasks'] if t.get('project_id')==row['id']]
                layout.addWidget(label(f"关联任务 {len(related)} 项 · 已完成 {sum(t.get('status')=='completed' for t in related)} 项",'Muted'))
                for task in related:layout.addWidget(self.task_row(task))
            if key=='reviews':layout.addWidget(label('下次复习：'+str(row.get('next_review_at') or '')[:16],'Muted'))
            if key!='weekly':layout.addWidget(button({'inbox':'转为任务','reviews':'复习反馈'}.get(key,'编辑项目'),lambda _,r=row:self.edit(key,r)),0,Qt.AlignLeft)
            box.addWidget(card)
        if not rows:box.addWidget(label('暂时没有内容，可以从上方新建。','Muted'))
        box.addStretch();self.body.addWidget(scroll,1)

    def render_knowledge(self):
        self.header('知识卡片','把论文结论、方法和易忘的细节，变成可以自测的一问一答。','＋ 新建卡片',lambda:self.edit_review(None))
        filters=QHBoxLayout()
        self.knowledge_search=QLineEdit(getattr(self,'knowledge_query',''))
        self.knowledge_search.setPlaceholderText('搜索问题、答案或来源…')
        self.knowledge_search.textChanged.connect(self.filter_knowledge)
        filters.addWidget(self.knowledge_search,1)
        self.knowledge_filter=QComboBox()
        self.knowledge_filter.addItems(['全部卡片','待自测'])
        self.knowledge_filter.setCurrentText(getattr(self,'knowledge_mode','全部卡片'))
        self.knowledge_filter.currentTextChanged.connect(self.filter_knowledge)
        filters.addWidget(self.knowledge_filter)
        self.body.addLayout(filters)
        due=sum(review_due(row) for row in self.data['reviews'])
        self.body.addWidget(label(f'共 {len(self.data["reviews"])} 张 · {due} 张待自测。先回想，再展开答案；无需每天打卡。','Muted'))
        scroll,self.knowledge_listing=scroll_content()
        self.body.addWidget(scroll,1)
        self.fill_knowledge()

    def filter_knowledge(self,_=None):
        self.knowledge_query=self.knowledge_search.text()
        self.knowledge_mode=self.knowledge_filter.currentText()
        self.fill_knowledge()

    def fill_knowledge(self):
        clear_layout(self.knowledge_listing)
        query=getattr(self,'knowledge_query','').casefold()
        rows=[r for r in self.data['reviews'] if query in ' '.join(str(r.get(k) or '') for k in ('title','note','source')).casefold()]
        if getattr(self,'knowledge_mode','全部卡片')=='待自测':rows=[r for r in rows if review_due(r)]
        for row in rows:
            card=QFrame();card.setObjectName('Card')
            box=QVBoxLayout(card);box.setContentsMargins(20,18,20,18);box.setSpacing(12)
            box.addWidget(label(row.get('title') or '未命名知识卡片','Section'))
            next_day=str(row.get('next_review_at') or '')[:10]
            meta='可以自测' if review_due(row) else '下次自测 '+next_day
            project=next((p.get('name','') for p in self.data['projects'] if p['id']==row.get('project_id')),'')
            if project:meta+=' · '+project
            box.addWidget(label(meta,'Muted'))
            answer=label(row.get('note') or '这是一条旧复习记录，还没有答案。可点击“编辑”补充，原内容会保留。')
            answer.setTextInteractionFlags(Qt.TextSelectableByMouse)
            answer.hide();box.addWidget(answer)
            if row.get('source'):box.addWidget(label('来源：'+row['source'],'Muted'))
            actions=QHBoxLayout()
            reveal=QPushButton('查看答案');reveal.setCheckable(True)
            actions.addWidget(reveal)
            again=button('还模糊',lambda _,r=row:self.rate_knowledge(r,False))
            remembered=button('记住了',lambda _,r=row:self.rate_knowledge(r,True))
            again.setEnabled(False);remembered.setEnabled(False)
            def flip(checked,a=answer,b=reveal,c=again,d=remembered,has_answer=bool(row.get('note'))):
                a.setVisible(checked);b.setText('收起答案' if checked else '查看答案')
                c.setEnabled(checked and has_answer);d.setEnabled(checked and has_answer)
            reveal.toggled.connect(flip)
            actions.addWidget(again);actions.addWidget(remembered)
            actions.addStretch()
            actions.addWidget(button('编辑',lambda _,r=row:self.edit_review(r)))
            box.addLayout(actions)
            self.knowledge_listing.addWidget(card)
        if not rows:self.knowledge_listing.addWidget(label('没有匹配的卡片。可以把刚学会的一个概念记成问题和答案。','Muted'))
        self.knowledge_listing.addStretch()

    def edit_review(self,row=None):
        record=row or {}
        dialog=QDialog(self);dialog.setWindowTitle('编辑知识卡片' if row else '新建知识卡片');dialog.resize(540,500)
        outer=QVBoxLayout(dialog)
        scroll,box=scroll_content();box.setContentsMargins(18,14,18,14);outer.addWidget(scroll,1)
        question=PlainTitleEdit(record.get('title') or '')
        question.setPlaceholderText('例如：这个方法为什么需要对照实验？')
        answer=QTextEdit();answer.setAcceptRichText(False);answer.setPlainText(record.get('note') or '');answer.setMinimumHeight(110)
        source=QLineEdit(record.get('source') or '')
        source.setPlaceholderText('论文标题、页码或链接（可选）')
        project=QComboBox();project.addItem('不关联项目',None)
        for p in self.data['projects']:project.addItem(p.get('name') or '未命名项目',p['id'])
        project.setCurrentIndex(max(0,project.findData(record.get('project_id'))))
        for text,widget in [('问题 / 知识点',question),('答案 / 理解',answer),('来源',source),('关联项目',project)]:
            box.addWidget(label(text,'Muted'));box.addWidget(widget)
        error=label('','Muted');box.addWidget(error)
        actions=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        actions.button(QDialogButtonBox.Save).setText('保存卡片');actions.button(QDialogButtonBox.Cancel).setText('取消')
        actions.button(QDialogButtonBox.Save).setObjectName('Primary')
        def accept():
            if not question.text().strip():error.setText('请填写问题或知识点。')
            else:dialog.accept()
        actions.accepted.connect(accept);actions.rejected.connect(dialog.reject);outer.addWidget(actions)
        if dialog.exec_()==QDialog.Accepted:
            self.upsert('reviews',{'title':question.text().strip(),'note':answer.toPlainText().strip(),'source':source.text().strip(),
                'project_id':project.currentData(),'next_review_at':record.get('next_review_at') or dt.datetime.now().isoformat(),
                'is_active':record.get('is_active',True)},row)

    def rate_knowledge(self,row,remembered):
        if self.upsert('reviews',review_feedback(row,remembered),row):
            self.set_sync_state('已记录自测，下次时间已更新。')

    def render_growth(self):
        summary=week_summary(self.data)
        self.header('成长记录',f"{summary['start'].strftime('%m.%d')} — {summary['today'].strftime('%m.%d')} · 已经做过的事情，也值得看见。",'记录本周心得',self.edit_weekly)
        scroll,box=scroll_content()
        stats=QHBoxLayout()
        for name,value in [('完成任务',str(len(summary['completed']))+' 项'),('专注时间',str(summary['minutes'])+' 分钟'),('推进项目',str(summary['project_count'])+' 个')]:
            card=QFrame();card.setObjectName('Card');inside=QVBoxLayout(card);inside.setContentsMargins(18,14,18,14)
            inside.addWidget(label(value,'Section'));inside.addWidget(label(name,'Muted'));stats.addWidget(card,1)
        box.addLayout(stats)
        box.addWidget(label('本周节奏','Section'))
        box.addWidget(label('只统计实际记录，不补造历史。专注按结束日期计入；旧任务若缺少完成时间，不计入本周。','Muted'))
        rhythm=QGridLayout()
        maximum=max(1,max(d['tasks'] for d in summary['days']))
        for i,day in enumerate(summary['days']):
            rhythm.addWidget(label('周'+'一二三四五六日'[i],'Muted'),i,0)
            bar=QProgressBar();bar.setRange(0,maximum);bar.setValue(day['tasks']);bar.setTextVisible(False)
            bar.setAccessibleName(f"周{'一二三四五六日'[i]}完成 {day['tasks']} 项")
            rhythm.addWidget(bar,i,1)
            text='尚未到来' if day['date']>summary['today'] else f"{day['tasks']} 项 · {day['seconds']//60} 分钟"
            rhythm.addWidget(label(text,'Muted'),i,2)
        rhythm.setColumnStretch(1,1);box.addLayout(rhythm)
        copy=button('复制本周进展',self.copy_week_report);box.addWidget(copy,0,Qt.AlignLeft)
        box.addWidget(label('完成足迹','Section'))
        for task in summary['completed']:box.addWidget(self.task_row(task))
        if not summary['completed']:box.addWidget(label('完成一件任务后，它会出现在这里。不必为了数字填满一天。','Muted'))
        box.addWidget(label('我的心得','Section'))
        notes=sorted(self.data['weekly_reviews'],key=lambda n:n.get('period_start') or '',reverse=True)
        for note in notes:
            card=QFrame();card.setObjectName('Card');inside=QVBoxLayout(card);inside.setContentsMargins(18,14,18,14)
            inside.addWidget(label(str(note.get('period_start') or '历史记录'),'Muted'))
            inside.addWidget(label(note.get('highlights') or '暂无心得'))
            if note.get('next_plan'):inside.addWidget(label('下一步：'+note['next_plan'],'Muted'))
            inside.addWidget(button('编辑心得',lambda _,r=note:self.edit_weekly(r)),0,Qt.AlignLeft)
            box.addWidget(card)
        if not notes:box.addWidget(label('可以写下一个收获、一个卡点，或者下一步。','Muted'))
        box.addStretch();self.body.addWidget(scroll,1)

    def copy_week_report(self):
        QApplication.clipboard().setText(week_report(self.data))
        self.set_sync_state('本周进展已复制，可粘贴到组会笔记。')

    def edit_weekly(self,row=None):
        if isinstance(row,bool):row=None
        start=week_summary(self.data)['start'].isoformat()
        record=row or next((n for n in self.data['weekly_reviews'] if n.get('period_start')==start),None)
        values=record or {}
        dialog=self.dialog('本周心得',[('highlights','收获 / 卡点','note',values.get('highlights') or ''),('next_plan','下一步','note',values.get('next_plan') or '')])
        if dialog:
            highlights=dialog.value('highlights');plan=dialog.value('next_plan')
            if not highlights and not plan:self.message('请至少写下一条心得或下一步。');return
            self.upsert('weekly_reviews',{'period_start':values.get('period_start') or start,'highlights':highlights,'next_plan':plan},record)

    def edit_inbox(self,row):
        if row:
            draft={'title':row.get('content',''),'start_date':dt.date.today().isoformat(),'end_date':dt.date.today().isoformat()}
            dialog=TaskEditor(self,draft)
            if dialog.exec_()==QDialog.Accepted and self.upsert('tasks',dialog.value()):self.upsert('inbox_items',{'status':'converted'},row)
        else:super().edit_inbox(row)

    def save_preferences(self):
        temp=self.settings_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,self.settings_path)

    def render_settings(self):
        self.header('设置','阅读习惯、提醒与数据安全。')
        scroll,box=scroll_content()
        form=QFormLayout()
        font=QSpinBox();font.setRange(14,24);font.setValue(self.settings.get('font_size',16));font.setSuffix(' px')
        compact=QCheckBox('减少列表留白');compact.setChecked(self.settings.get('compact_mode',False))
        notifications=QCheckBox('启用桌面任务提醒');notifications.setChecked(self.settings.get('notifications_enabled',True))
        tray=QCheckBox('关闭窗口时留在系统托盘');tray.setChecked(self.settings.get('close_to_tray',False))
        form.addRow('正文大小',font);form.addRow('信息密度',compact);form.addRow('提醒',notifications);form.addRow('后台运行',tray)
        box.addLayout(form)
        box.addWidget(label('提醒需要研序保持运行。完全退出或电脑关机后不会提醒。','Muted'))
        def save():
            self.settings.update(font_size=font.value(),compact_mode=compact.isChecked(),notifications_enabled=notifications.isChecked(),close_to_tray=tray.isChecked())
            self.save_preferences();self.setStyleSheet(self.style());self.setup_notifications()
        box.addWidget(button('保存偏好',save,True))
        box.addSpacing(18);box.addWidget(label('数据与备份','Section'))
        box.addWidget(label('内容立即保存到本机；每日首次启动自动备份。恢复前会另存当前数据库。','Muted'))
        box.addWidget(button('导出数据备份…',self.export_backup))
        box.addWidget(button('从备份恢复…',self.restore_backup))
        box.addWidget(label('数据位置：'+str(self.directory),'Muted'))
        box.addSpacing(18);box.addWidget(label('账户与更新','Section'))
        box.addWidget(label('本版无需登录。云端同步暂不启用，原账户和缓存保持不变。','Muted'))
        box.addWidget(label('版本 '+VERSION+' · 本轮为本地桌面预览，暂不自动安装云端旧版。','Muted'))
        box.addStretch();self.body.addWidget(scroll,1)

    def export_backup(self):
        path,_=QFileDialog.getSaveFileName(self,'导出数据备份','YanXu-backup-'+dt.date.today().isoformat()+'.json','研序备份 (*.json)')
        if path:
            try:self.store.export(path);QMessageBox.information(self,'备份完成','已导出任务等业务数据，不含账号令牌。')
            except Exception as error:self.message(str(error))

    def restore_backup(self):
        path,_=QFileDialog.getOpenFileName(self,'选择研序备份','','研序备份 (*.json)')
        if not path:return
        if QMessageBox.question(self,'恢复备份','将以备份内容替换当前本地数据。当前数据会先自动备份，是否继续？')!=QMessageBox.Yes:return
        try:self.store.restore(path);self.undo_action=None;self.refresh()
        except Exception as error:self.message(str(error))

    def start_focus(self,task=None):
        if self.focus_task is not None:
            self.set_sync_state('已有专注计时，请先结束当前专注。');return
        self.focus_task=task or {}
        self.focus_elapsed=0
        self.focus_started=time.monotonic()
        self.render(self.active_key)

    def toggle_focus(self):
        if self.focus_task is None:self.start_focus();return
        if self.focus_started is None:self.focus_started=time.monotonic()
        else:self.focus_elapsed+=time.monotonic()-self.focus_started;self.focus_started=None
        self.update_focus()

    def update_focus(self):
        if not hasattr(self,'focus_label') or self.active_key=='settings':return
        seconds=int(self.focus_elapsed+(time.monotonic()-self.focus_started if self.focus_started is not None else 0))
        self.focus_label.setText(f'专注 {seconds//60:02d}:{seconds%60:02d}' if self.focus_task is not None else '')
        self.focus_button.setText('开始专注' if self.focus_task is None else ('继续' if self.focus_started is None else '暂停'))

    def finish_focus(self):
        if self.focus_task is None:return True
        seconds=int(self.focus_elapsed+(time.monotonic()-self.focus_started if self.focus_started is not None else 0))
        ended=dt.datetime.now()
        try:
            self.store.upsert('focus',{'task_id':self.focus_task.get('id'),'started_at':(ended-dt.timedelta(seconds=seconds)).isoformat(),'ended_at':ended.isoformat(),'duration_minutes':seconds//60,'duration_seconds':seconds})
        except Exception as error:self.message('专注记录未保存：'+str(error));return False
        self.focus_task=None;self.focus_started=None;self.focus_elapsed=0;self.refresh();return True

    def edit_focus(self,selected_task=None):self.start_focus(selected_task)

    def setup_notifications(self):
        if self.tray is None and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray=QSystemTrayIcon(self.windowIcon(),self)
            self.tray.setToolTip('研序 YanXu')
            menu=QMenu(self)
            menu.addAction('打开研序',self.restore_window)
            menu.addAction('退出研序',self.quit_app)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason:self.restore_window() if reason==QSystemTrayIcon.DoubleClick else None)
        if self.tray:
            self.tray.setVisible(bool(self.settings.get('notifications_enabled') or self.settings.get('close_to_tray')))
        if not hasattr(self,'reminder_timer'):
            self.reminder_timer=QTimer(self)
            self.reminder_timer.setInterval(30000)
            self.reminder_timer.timeout.connect(self.check_reminders)
        if self.settings.get('notifications_enabled'):
            self.reminder_timer.start()
        else:
            self.reminder_timer.stop()

    def check_reminders(self):
        if not self.settings.get('notifications_enabled') or not self.tray:return
        now=dt.datetime.now()
        for task in self.data['tasks']:
            policy=task.get('reminder_policy') or {}
            if not policy.get('enabled',True) or task.get('status') in ('completed','cancelled') or not task.get('start_time'):continue
            try:when=dt.datetime.fromisoformat(task['start_date']+'T'+task['start_time'][:5])-dt.timedelta(minutes=int(policy.get('minutes_before',10)))
            except (KeyError,ValueError,TypeError):continue
            key=f"{task['id']}:{when.isoformat()}"
            if key not in self.notified and 0<=(now-when).total_seconds()<90:
                self.tray.showMessage('任务提醒',task.get('title','任务'),QSystemTrayIcon.Information,7000);self.notified.add(key)

    def restore_window(self):self.showNormal();self.raise_();self.activateWindow()

    def quit_app(self):
        self.exiting=True
        self.close()

    def closeEvent(self,event):
        if self.settings.get('close_to_tray') and self.tray and self.tray.isVisible() and not getattr(self,'exiting',False):
            self.hide();event.ignore();return
        if not self.finish_focus():event.ignore();return
        try:
            self.settings['geometry']=bytes(self.saveGeometry().toHex()).decode('ascii')
            self.save_preferences()
        except OSError as error:self.message('设置未能保存：'+str(error));event.ignore();return
        self.store.close()
        self.focus_timer.stop()
        self.reminder_timer.stop()
        if self.tray:self.tray.hide()
        event.accept()


if __name__=='__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app=QApplication(sys.argv)
    app.setApplicationName('研序 YanXu')
    app.setFont(QFont('Microsoft YaHei UI',11))
    try:
        test_directory = None
        if '--smoke-test' in sys.argv:
            index = sys.argv.index('--smoke-test')
            test_directory = sys.argv[index+1]
        data_directory=Path(test_directory or APP_DIR)
        data_directory.mkdir(parents=True,exist_ok=True)
        instance_lock=QLockFile(str(data_directory/'desktop.lock'))
        if not instance_lock.tryLock(100):
            QMessageBox.information(None,'研序已在运行','请使用已打开的研序窗口，或从系统托盘打开。')
            sys.exit(0)
        window=DesktopWindow(test_directory)
        window.show()
        if test_directory:
            QTimer.singleShot(2000, window.close)
        sys.exit(app.exec_())
    except Exception as error:
        QMessageBox.critical(None,'研序启动失败','未修改原有云端缓存。请保留数据目录以便恢复。\n'+str(error))
        raise
