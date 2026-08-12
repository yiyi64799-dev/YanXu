"""YanXu V2 desktop client.  Cloud-first so the same account stays in sync with mobile."""
import datetime as dt
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from PyQt5.QtCore import QDate, QPointF, QRectF, QSize, Qt, QTime, QTimer, QUrl
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDateEdit,
    QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QProgressDialog, QSizePolicy, QSpinBox, QStackedWidget, QSystemTrayIcon, QTextEdit, QTimeEdit,
    QVBoxLayout, QWidget)

APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.abspath(".")), "YanXu")
SETTINGS = os.path.join(APP_DIR, "settings.json")
CACHE = os.path.join(APP_DIR, "v2-cache.json")
OLD_SETTINGS = os.path.join(os.environ.get("LOCALAPPDATA", os.path.abspath(".")), "FocusCalendar", "settings.json")
APP_VERSION = "2.2.0"
TOKENS = {
    "canvas": "#F6F8F7", "sidebar": "#F1F6F4", "surface": "#FFFFFF",
    "primary": "#176B5B", "primary_hover": "#125A4C", "primary_soft": "#E7F3EF",
    "ink": "#17201E", "muted": "#66736F", "faint": "#8A9692",
    "border": "#DDE7E3", "warning": "#B86A24", "danger": "#B9473F",
}
GREEN, SOFT, INK, MUTED, PAPER = TOKENS["primary"], TOKENS["primary_soft"], TOKENS["ink"], TOKENS["muted"], TOKENS["surface"]

APPEARANCES = {
    "薄雾绿": ("#F6F8F7", "#F1F6F4"),
    "暖纸白": ("#FAF8F3", "#F5F1E8"),
    "宁静灰": ("#F5F6F7", "#EFF2F3"),
}


def resource_path(relative):
    base = getattr(__import__("sys"), "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget: widget.hide(); widget.setParent(None); widget.deleteLater()
        elif item.layout(): clear_layout(item.layout())


def make_icon(kind, color=INK, size=18):
    pixmap = QPixmap(size, size); pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.7); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin); painter.setPen(pen)
    if kind == "today":
        painter.drawEllipse(QRectF(5, 5, 8, 8)); painter.drawLine(QPointF(9,1.5),QPointF(9,3)); painter.drawLine(QPointF(9,15),QPointF(9,16.5)); painter.drawLine(QPointF(1.5,9),QPointF(3,9)); painter.drawLine(QPointF(15,9),QPointF(16.5,9))
    elif kind == "tasks":
        painter.drawEllipse(QRectF(2.5, 2.5, 13, 13)); painter.drawLine(QPointF(5.5,9),QPointF(8,11.5)); painter.drawLine(QPointF(8,11.5),QPointF(13,6))
    elif kind == "projects":
        painter.drawRoundedRect(QRectF(2, 5, 14, 10.5), 2, 2); painter.drawLine(3, 5, 7, 5); painter.drawLine(QPointF(7,5),QPointF(8.5,3.5)); painter.drawLine(QPointF(8.5,3.5),QPointF(13,3.5))
    elif kind == "reviews":
        painter.drawRoundedRect(QRectF(3, 2.5, 12, 13), 1.5, 1.5); painter.drawLine(6, 6, 12, 6); painter.drawLine(6, 9, 12, 9); painter.drawLine(6, 12, 10, 12)
    elif kind == "inbox":
        painter.drawRoundedRect(QRectF(2.5, 3.5, 13, 11.5), 2, 2); painter.drawLine(QPointF(3,11),QPointF(6.5,11)); painter.drawLine(QPointF(6.5,11),QPointF(8,13)); painter.drawLine(8,13,10,11); painter.drawLine(10,11,15,11)
    elif kind == "calendar":
        painter.drawRoundedRect(QRectF(2.5, 3.5, 13, 12), 2, 2); painter.drawLine(QPointF(2.5,7),QPointF(15.5,7)); painter.drawLine(6,2,6,5); painter.drawLine(12,2,12,5)
    elif kind == "weekly":
        painter.drawLine(3, 15, 3, 10); painter.drawLine(7, 15, 7, 6); painter.drawLine(11, 15, 11, 9); painter.drawLine(15, 15, 15, 3)
    else:
        painter.drawLine(3, 5, 15, 5); painter.drawEllipse(QRectF(6, 3, 4, 4)); painter.drawLine(3, 9, 15, 9); painter.drawEllipse(QRectF(10, 7, 4, 4)); painter.drawLine(3, 13, 15, 13); painter.drawEllipse(QRectF(4, 11, 4, 4))
    painter.end(); return QIcon(pixmap)


class NavButton(QPushButton):
    def __init__(self, key, text, parent=None):
        super().__init__(text, parent); self.key = key; self.setCheckable(True); self.setFixedHeight(46); self.setIconSize(QSize(20, 20)); self.setCursor(Qt.PointingHandCursor); self.setObjectName("NavButton"); self.toggled.connect(self.refresh_icon); self.refresh_icon(False)
    def refresh_icon(self, checked): self.setIcon(make_icon(self.key, GREEN if checked else MUTED))


class TaskCard(QFrame):
    def __init__(self, task, project_name="", focus_callback=None, edit_callback=None, parent=None):
        super().__init__(parent); self.setObjectName("TaskCard"); self.setCursor(Qt.PointingHandCursor); layout = QHBoxLayout(self); layout.setContentsMargins(16, 12, 14, 12); layout.setSpacing(12)
        done = QCheckBox(); done.setObjectName("DoneCircle"); done.setChecked(task.get("status") == "completed"); done.setEnabled(False); layout.addWidget(done, 0, Qt.AlignVCenter)
        copy = QVBoxLayout(); copy.setSpacing(4); title = QLabel(task.get("title") or "未命名任务"); title.setObjectName("TaskTitle"); copy.addWidget(title)
        start = (task.get("start_time") or "").strip(); end = (task.get("end_time") or "").strip(); time = f"{start[:5]}–{end[:5]}" if start and end else (start[:5] if start else "未安排时间")
        parts = [time];
        if project_name: parts.append(project_name)
        if task.get("estimated_minutes"): parts.append(f"预计 {task['estimated_minutes']}min")
        meta = QLabel("  ·  ".join(parts)); meta.setObjectName("MetaText"); copy.addWidget(meta); layout.addLayout(copy, 1)
        status_map = {"pending":"待开始","in_progress":"进行中","waiting":"等待","blocked":"阻塞","completed":"已完成","cancelled":"已取消"}
        tag = QLabel(status_map.get(task.get("status"), "待开始")); tag.setObjectName("StatusTag"); tag.setProperty("state", task.get("status") or "pending"); layout.addWidget(tag, 0, Qt.AlignVCenter)
        if focus_callback and task.get("status") not in ("completed", "cancelled", "blocked"):
            focus = QPushButton("开始专注"); focus.setObjectName("Secondary"); focus.setCursor(Qt.PointingHandCursor); focus.clicked.connect(lambda: focus_callback(task)); layout.addWidget(focus, 0, Qt.AlignVCenter)
        if edit_callback: self.mouseDoubleClickEvent = lambda _event: edit_callback(task)


class TodayPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("ContentCanvas"); self.layout=QVBoxLayout(self); self.layout.setContentsMargins(32,20,32,20); self.layout.setSpacing(14)
    def render_dashboard(self, tasks, projects, reviews, inbox_items, create_task, start_focus, edit_task, goto_page):
        clear_layout(self.layout); today = dt.date.today(); week = "一二三四五六日"[today.weekday()]
        header = QHBoxLayout(); header.setSpacing(16); copy = QVBoxLayout(); copy.setSpacing(2)
        date_label = QLabel(f"{today.month} 月 {today.day} 日 · 周{week}"); date_label.setObjectName("Eyebrow"); copy.addWidget(date_label)
        title = QLabel("今日"); title.setObjectName("PageTitle"); copy.addWidget(title); hint = QLabel("今天只推进最重要的一步。"); hint.setObjectName("BodyMuted"); copy.addWidget(hint); header.addLayout(copy); header.addStretch()
        add = QPushButton("＋  新建任务"); add.setObjectName("Primary"); add.setFixedHeight(40); add.setCursor(Qt.PointingHandCursor); add.clicked.connect(create_task); header.addWidget(add, 0, Qt.AlignTop); self.layout.addLayout(header)
        today_key = today.isoformat(); active = [x for x in tasks if x.get("start_date", today_key) <= today_key <= x.get("end_date", today_key) and x.get("status") not in ("completed","cancelled")]
        rank = {"today":0,"high":1,"normal":2,"low":3}; highlights = sorted(active, key=lambda x:(rank.get(x.get("priority"),2), x.get("start_time") or "99:99"))[:3]
        due_reviews = [x for x in reviews if x.get("is_active",True) and x.get("next_review_at","") <= dt.datetime.now().isoformat()]
        active_projects = [x for x in projects if x.get("status") == "active"][:3]
        summary = QHBoxLayout(); summary.setSpacing(10)
        for label, value in (("今日",len(active)),("待复习",len(due_reviews)),("进行中项目",len(active_projects))):
            card=QFrame(); card.setObjectName("SummaryCard"); card.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed); box=QVBoxLayout(card); box.setContentsMargins(14,8,14,8); box.setSpacing(0); number=QLabel(str(value)); number.setObjectName("SummaryNumber"); caption=QLabel(label); caption.setObjectName("MetaText"); box.addWidget(number); box.addWidget(caption); summary.addWidget(card)
        summary.addStretch(); self.layout.addLayout(summary)
        section = QLabel("今日重点"); section.setObjectName("SectionTitle"); self.layout.addWidget(section)
        if highlights:
            highlight_card = QFrame(); highlight_card.setObjectName("Card"); highlight_layout = QVBoxLayout(highlight_card); highlight_layout.setContentsMargins(6,6,6,6); highlight_layout.setSpacing(6)
            for task in highlights: highlight_layout.addWidget(TaskCard(task, next((p.get("name","") for p in projects if p.get("id") == task.get("project_id")), ""), start_focus, edit_task))
            self.layout.addWidget(highlight_card)
        else:
            empty=QFrame(); empty.setObjectName("EmptyState"); empty.setMaximumHeight(126); ebox=QVBoxLayout(empty); ebox.setContentsMargins(20,12,20,12); ebox.setSpacing(4); et=QLabel("今天还没有重点任务"); et.setObjectName("ModuleTitle"); es=QLabel("可以从 Inbox 选择一件事情开始，或者新建一个小而明确的行动。"); es.setObjectName("BodyMuted"); eb=QPushButton("＋ 添加今日重点"); eb.setObjectName("Secondary"); eb.clicked.connect(create_task); ebox.addWidget(et); ebox.addWidget(es); ebox.addWidget(eb,0,Qt.AlignLeft); self.layout.addWidget(empty)
        lower = QGridLayout(); lower.setHorizontalSpacing(14); lower.setVerticalSpacing(10); lower.setColumnStretch(0,2); lower.setColumnStretch(1,1); lower.setRowStretch(0,1); lower.setRowStretch(1,1)
        schedule = QFrame(); schedule.setObjectName("Card"); schedule.setMinimumHeight(210); schedule.setMaximumHeight(280); sbox=QVBoxLayout(schedule); sbox.setContentsMargins(18,14,18,14); sbox.setSpacing(8); st=QLabel("今日安排"); st.setObjectName("SectionTitle"); sbox.addWidget(st)
        if active:
            for task in sorted(active,key=lambda x:x.get("start_time") or "99:99")[:3]: sbox.addWidget(TaskCard(task,next((p.get("name","") for p in projects if p.get("id")==task.get("project_id")),""),None,edit_task))
            sbox.addStretch()
        else:
            sbox.addStretch(); no=QLabel("今天没有排定时间。\n可以从 Inbox 选择一件事情开始。"); no.setObjectName("BodyMuted"); no.setWordWrap(True); no.setAlignment(Qt.AlignCenter); sbox.addWidget(no); choose=QPushButton("查看 Inbox"); choose.setObjectName("Tertiary"); choose.clicked.connect(lambda:goto_page("inbox")); sbox.addWidget(choose,0,Qt.AlignCenter); sbox.addStretch()
        lower.addWidget(schedule,0,0,2,1)
        review_card=QFrame(); review_card.setObjectName("Card"); rbox=QVBoxLayout(review_card); rbox.setContentsMargins(16,12,16,12); rbox.setSpacing(3); rt=QLabel("待复习"); rt.setObjectName("ModuleTitle"); rbox.addWidget(rt); rv=QLabel(f"{len(due_reviews)} 个知识点"); rv.setObjectName("MetricText"); rbox.addWidget(rv); rs=QLabel("用几分钟巩固已经学过的内容。" if due_reviews else "今天没有到期复习。"); rs.setObjectName("BodyMuted"); rs.setWordWrap(True); rbox.addWidget(rs); rbox.addStretch(); rb=QPushButton("查看复习"); rb.setObjectName("Tertiary"); rb.clicked.connect(lambda:goto_page("reviews")); rbox.addWidget(rb,0,Qt.AlignLeft); lower.addWidget(review_card,0,1)
        project_card=QFrame(); project_card.setObjectName("Card"); pbox=QVBoxLayout(project_card); pbox.setContentsMargins(16,12,16,12); pbox.setSpacing(3); pt=QLabel("项目推进"); pt.setObjectName("ModuleTitle"); pbox.addWidget(pt)
        if active_projects:
            for project in active_projects:
                row=QHBoxLayout(); name=QLabel(project.get("name") or "未命名项目"); name.setObjectName("BodyText"); progress=QLabel(f"{project.get('progress',0)}%"); progress.setObjectName("MetaText"); row.addWidget(name,1); row.addWidget(progress); pbox.addLayout(row); nxt=QLabel("下一步："+(project.get("next_action") or "尚未设置")); nxt.setObjectName("MetaText"); nxt.setWordWrap(True); pbox.addWidget(nxt)
        else:
            ps=QLabel("还没有进行中的项目。"); ps.setObjectName("BodyMuted"); pbox.addWidget(ps)
        pbox.addStretch(); pb=QPushButton("查看项目"); pb.setObjectName("Tertiary"); pb.clicked.connect(lambda:goto_page("projects")); pbox.addWidget(pb,0,Qt.AlignLeft); lower.addWidget(project_card,1,1); self.layout.addLayout(lower,1)


class SettingsPage(QWidget):
    """A first-class settings centre instead of a database-connection form."""
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.setObjectName("ContentCanvas")
        shell = QVBoxLayout(self); shell.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setObjectName("DashboardScroll"); shell.addWidget(scroll)
        content = QWidget(); content.setObjectName("ContentCanvas"); self.body = QVBoxLayout(content); self.body.setContentsMargins(32,26,32,36); self.body.setSpacing(18); scroll.setWidget(content)
        head = QHBoxLayout(); copy = QVBoxLayout(); copy.setSpacing(5)
        eyebrow = QLabel("PREFERENCES"); eyebrow.setObjectName("Eyebrow"); copy.addWidget(eyebrow)
        title = QLabel("设置"); title.setObjectName("PageTitle"); copy.addWidget(title)
        intro = QLabel("让研序更适合你的阅读习惯、工作节奏与设备环境。"); intro.setObjectName("BodyMuted"); copy.addWidget(intro)
        head.addLayout(copy); head.addStretch(); save = QPushButton("保存更改"); save.setObjectName("Primary"); save.clicked.connect(self.save_preferences); head.addWidget(save, 0, Qt.AlignTop); self.body.addLayout(head)

        self.font_size = QSpinBox(); self.font_size.setRange(14, 32); self.font_size.setSingleStep(1); self.font_size.setSuffix(" px")
        self.appearance = QComboBox(); self.appearance.addItems(APPEARANCES.keys())
        self.compact = QCheckBox("使用紧凑任务卡片")
        self.body.addWidget(self.card("外观与阅读", "字体、密度与界面底色会立即应用到整个软件。", [
            ("界面字号", self.font_size, "可在 14–32px 之间逐级调整。"),
            ("背景颜色", self.appearance, "低对比度背景可减少长时间使用的视觉疲劳。"),
            ("信息密度", self.compact, "在较小窗口中显示更多内容。"),
        ]))

        self.notifications = QCheckBox("允许桌面通知"); self.task_reminders = QCheckBox("任务开始前提醒")
        self.reminder_minutes = QSpinBox(); self.reminder_minutes.setRange(0, 240); self.reminder_minutes.setSuffix(" 分钟")
        self.daily_summary = QCheckBox("每天首次打开时显示今日概览")
        self.body.addWidget(self.card("提醒与通知", "研序仅为到期任务发送轻量提醒，不会频繁打扰。", [
            ("通知权限", self.notifications, "关闭后不会弹出任何系统提醒。"),
            ("任务提醒", self.task_reminders, "按照任务日期和开始时间触发。"),
            ("默认提前", self.reminder_minutes, "未单独配置提醒策略的任务使用此时间。"),
            ("每日概览", self.daily_summary, "每天只显示一次。"),
        ]))

        self.sync_state = QLabel(); self.sync_state.setObjectName("BodyText")
        self.account_state = QLabel(); self.account_state.setObjectName("MetaText")
        sync_now = QPushButton("立即同步"); sync_now.setObjectName("Secondary"); sync_now.clicked.connect(owner.refresh)
        account = QPushButton("账户与连接"); account.setObjectName("Secondary"); account.clicked.connect(owner.edit_settings)
        self.body.addWidget(self.card("账户与跨端同步", "电脑与手机使用同一账号；共享空间数据由云端保持一致。", [
            ("当前状态", self.sync_state, "任务与项目共享；复习、Inbox 和专注记录保持个人私有。"),
            ("登录账号", self.account_state, "访问令牌只保存在当前设备。"),
            ("同步操作", self.button_row(sync_now, account), "网络不可用时继续使用本地缓存。"),
        ]))

        self.auto_update = QCheckBox("自动检查更新")
        self.update_channel = QComboBox(); self.update_channel.addItem("稳定版", "stable"); self.update_channel.addItem("预览版", "preview")
        self.update_state = QLabel(f"当前版本 v{APP_VERSION}"); self.update_state.setObjectName("BodyText")
        check = QPushButton("检查更新"); check.setObjectName("Secondary"); check.clicked.connect(lambda: owner.check_updates(True))
        self.download_update = QPushButton("下载更新"); self.download_update.setObjectName("Primary"); self.download_update.clicked.connect(owner.download_update); self.download_update.hide()
        self.release_notes = QLabel("暂无更新说明"); self.release_notes.setObjectName("MetaText"); self.release_notes.setWordWrap(True); self.release_notes.setMaximumWidth(420)
        self.body.addWidget(self.card("系统更新", "更新检查只读取版本信息，不会自动安装或覆盖你的数据。", [
            ("版本", self.button_row(self.update_state, check, self.download_update), "如有新版本，将在确认后再下载安装。"),
            ("更新说明", self.release_notes, "发布说明来自统一版本清单。"),
            ("更新策略", self.auto_update, "启动后静默检查一次。"),
            ("更新通道", self.update_channel, "稳定版适合日常长期使用。"),
        ]))
        self.body.addStretch(); self.load_preferences()

    def card(self, title, description, rows):
        frame = QFrame(); frame.setObjectName("SettingsCard"); layout = QVBoxLayout(frame); layout.setContentsMargins(22, 20, 22, 20); layout.setSpacing(0)
        heading = QLabel(title); heading.setObjectName("SectionTitle"); layout.addWidget(heading)
        sub = QLabel(description); sub.setObjectName("BodyMuted"); sub.setWordWrap(True); layout.addWidget(sub); layout.addSpacing(14)
        for index, (label, control, help_text) in enumerate(rows):
            if index: line = QFrame(); line.setObjectName("Divider"); line.setFixedHeight(1); layout.addWidget(line)
            row = QHBoxLayout(); row.setContentsMargins(0, 11, 0, 11); row.setSpacing(20); text = QVBoxLayout(); text.setSpacing(3)
            name = QLabel(label); name.setObjectName("SettingLabel"); hint = QLabel(help_text); hint.setObjectName("MetaText"); hint.setWordWrap(True); text.addWidget(name); text.addWidget(hint); row.addLayout(text, 1); row.addWidget(control, 0, Qt.AlignVCenter); layout.addLayout(row)
        return frame

    def button_row(self, *widgets):
        holder = QWidget(); holder.setObjectName("Transparent"); row = QHBoxLayout(holder); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(8)
        for widget in widgets: row.addWidget(widget)
        return holder

    def load_preferences(self):
        size = int(self.owner.settings.get("font_size", 20)); self.font_size.setValue(size)
        self.appearance.setCurrentText(self.owner.settings.get("appearance", "薄雾绿")); self.compact.setChecked(bool(self.owner.settings.get("compact_mode", False)))
        self.notifications.setChecked(bool(self.owner.settings.get("notifications_enabled", True))); self.task_reminders.setChecked(bool(self.owner.settings.get("task_reminders", True)))
        self.reminder_minutes.setValue(int(self.owner.settings.get("reminder_minutes", 10))); self.daily_summary.setChecked(bool(self.owner.settings.get("daily_summary", True)))
        self.auto_update.setChecked(bool(self.owner.settings.get("auto_update", True))); channel = self.update_channel.findData(self.owner.settings.get("update_channel", "stable")); self.update_channel.setCurrentIndex(max(0, channel)); self.refresh_status()

    def refresh_status(self):
        cloud_ok = self.owner.cloud.ok(); self.sync_state.setText("已连接 · 可跨端同步" if cloud_ok else "仅本机 · 尚未连接")
        self.account_state.setText(self.owner.settings.get("supabase_email") or "尚未登录")
        self.update_state.setText(self.owner.update_message or f"当前版本 v{APP_VERSION}")
        update = self.owner.available_update
        self.download_update.setVisible(bool(update))
        self.release_notes.setText(str(update.get("release_notes") or "暂无更新说明") if update else "暂无更新说明")

    def save_preferences(self):
        self.owner.settings.update({
            "font_size": self.font_size.value(), "appearance": self.appearance.currentText(), "compact_mode": self.compact.isChecked(),
            "notifications_enabled": self.notifications.isChecked(), "task_reminders": self.task_reminders.isChecked(), "reminder_minutes": self.reminder_minutes.value(),
            "daily_summary": self.daily_summary.isChecked(), "auto_update": self.auto_update.isChecked(), "update_channel": self.update_channel.currentData(),
        })
        save_settings(self.owner.settings); self.owner.apply_preferences(); self.owner.setup_notifications(); self.owner.set_sync_state("设置已保存"); self.refresh_status()


def load_settings():
    for path in (SETTINGS, OLD_SETTINGS):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_settings(value):
    os.makedirs(APP_DIR, exist_ok=True)
    temp = SETTINGS + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(temp, SETTINGS)


class Cloud:
    def __init__(self, settings): self.settings = settings
    def ok(self): return bool(self.settings.get("supabase_url") and self.settings.get("supabase_key") and self.settings.get("supabase_access_token"))
    def request(self, method, path, payload=None, prefer=""):
        base = self.settings.get("supabase_url", "").rstrip("/")
        headers = {"apikey": self.settings.get("supabase_key", ""), "Content-Type": "application/json"}
        token = self.settings.get("supabase_access_token", "")
        if token: headers["Authorization"] = "Bearer " + token
        if prefer: headers["Prefer"] = prefer
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        context = ssl.create_default_context()
        if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
            context.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        last_error = ""
        for attempt in range(3):
            try:
                req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=20, context=context) as response:
                    raw = response.read().decode("utf-8", "replace")
                    return json.loads(raw) if raw else None, ""
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and path != "/auth/v1/token?grant_type=refresh_token" and self.refresh_session():
                    headers["Authorization"] = "Bearer " + self.settings.get("supabase_access_token", ""); continue
                return None, exc.read().decode("utf-8", "replace")
            except (urllib.error.URLError, ssl.SSLError, ConnectionError, OSError) as exc:
                last_error = str(getattr(exc, "reason", exc))
                if attempt < 2: time.sleep(0.4)
        return None, last_error or "网络连接失败"
    def refresh_session(self):
        refresh = self.settings.get("supabase_refresh_token", "")
        if not refresh: return False
        base = self.settings.get("supabase_url", "").rstrip("/"); body=json.dumps({"refresh_token":refresh}).encode("utf-8")
        headers={"apikey":self.settings.get("supabase_key", ""),"Content-Type":"application/json"}
        try:
            req=urllib.request.Request(base+"/auth/v1/token?grant_type=refresh_token",data=body,headers=headers,method="POST")
            with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as response: data=json.loads(response.read().decode("utf-8"))
            self.settings["supabase_access_token"]=data.get("access_token",""); self.settings["supabase_refresh_token"]=data.get("refresh_token",refresh); save_settings(self.settings); return bool(self.settings["supabase_access_token"])
        except Exception: return False
    def sign_in(self, email, password):
        data, err = self.request("POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password})
        if err or not data: return err or "登录失败"
        user = data.get("user", {})
        self.settings.update({"supabase_access_token": data.get("access_token", ""), "supabase_refresh_token": data.get("refresh_token", ""), "supabase_user_id": user.get("id", "")})
        save_settings(self.settings); return ""


class Editor(QDialog):
    def __init__(self, title, fields, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.resize(520, 620); self.setMinimumSize(460, 480); self.setMaximumSize(620, 720); self.widgets = {}
        layout = QVBoxLayout(self); layout.setContentsMargins(20,18,20,18); layout.setSpacing(12)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_host = QWidget(); form_host.setObjectName("Transparent"); form = QFormLayout(form_host); form.setContentsMargins(2,2,6,2); form.setHorizontalSpacing(14); form.setVerticalSpacing(9); form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); scroll.setWidget(form_host); layout.addWidget(scroll,1)
        for key, label, kind, value in fields:
            if kind == "text": w = QLineEdit(str(value or ""))
            elif kind == "note": w = QTextEdit(str(value or "")); w.setMinimumHeight(70)
            elif kind == "number": w = QSpinBox(); w.setRange(0, 10000); w.setValue(int(value or 0))
            elif kind == "choice":
                w = QComboBox(); w.addItems(label[1]); w.setCurrentText(str(value or label[1][0])); label = label[0]
            elif kind == "date":
                w = QDateEdit(); w.setCalendarPopup(True); w.setDisplayFormat("yyyy-MM-dd"); w.setDate(QDate.fromString(value or dt.date.today().isoformat(), "yyyy-MM-dd"))
            elif kind == "time":
                w = QTimeEdit(); w.setDisplayFormat("HH  mm"); w.setTime(QTime.fromString((value or "09:00")[:5], "HH:mm")); w.setButtonSymbols(QSpinBox.UpDownArrows)
            else: continue
            self.widgets[key] = w; form.addRow(label, w)
        buttons = QHBoxLayout(); buttons.setSpacing(10); cancel = QPushButton("取消"); cancel.setObjectName("Secondary"); ok = QPushButton("保存"); ok.setObjectName("Primary")
        cancel.clicked.connect(self.reject); ok.clicked.connect(self.accept); buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(ok); layout.addLayout(buttons)
    def value(self, key):
        w = self.widgets[key]
        if isinstance(w, QTextEdit): return w.toPlainText().strip()
        if isinstance(w, QSpinBox): return w.value()
        if isinstance(w, QComboBox): return w.currentText()
        if isinstance(w, QDateEdit): return w.date().toString("yyyy-MM-dd")
        if isinstance(w, QTimeEdit): return w.time().toString("HH:mm")
        return w.text().strip()


class YanXu(QMainWindow):
    def __init__(self):
        super().__init__(); self.settings = load_settings()
        changed=False
        if int(self.settings.get("font_size",20)) < 20: self.settings["font_size"]=20; changed=True
        for stale in ("ui_scale","visual_scale_v2"):
            if stale in self.settings: self.settings.pop(stale); changed=True
        if changed: save_settings(self.settings)
        self.cloud = Cloud(self.settings); self.data = self.load_cache(); self.space_id = self.settings.get("supabase_space_id", ""); self.sync_error = ""; self.update_message = ""; self.available_update = None; self.notified = set(); self.tray = None
        self.setWindowTitle("研序 YanXu"); self.setWindowIcon(QIcon(resource_path("assets/yanxu-logo-1024.png"))); self.resize(1160,760); self.setMinimumSize(940,650); self.setStyleSheet(self.style()); self.build(); self.center_window(); self.setup_notifications(); self.refresh()
        if self.settings.get("auto_update", True): QTimer.singleShot(4500, lambda: self.check_updates(False))
    def center_window(self):
        screen=QApplication.primaryScreen()
        if screen:
            area=screen.availableGeometry(); frame=self.frameGeometry(); frame.moveCenter(area.center()); self.move(frame.topLeft())
    def style(self):
        base=int(self.settings.get("font_size",20)); appearance=self.settings.get("appearance","薄雾绿"); canvas,sidebar=APPEARANCES.get(appearance,APPEARANCES["薄雾绿"]); compact_height=54 if self.settings.get("compact_mode",False) else max(66,base*4)
        stylesheet="""
        QMainWindow, QWidget { background: #F6F8F7; color: #17201E; font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "Noto Sans CJK SC"; font-size: 14px; }
        QLabel, QCheckBox { background: transparent; }
        QFrame#Sidebar { background: #F1F6F4; border-right: 1px solid #DDE7E3; }
        QLabel#BrandName { color: #17201E; font-size: 24px; font-weight: 600; }
        QLabel#BrandTagline { color: #788580; font-size: 9px; letter-spacing: .25px; }
        QPushButton#NavButton { min-height: 46px; max-height: 46px; border: 0; border-radius: 9px; padding: 0 8px; text-align: center; color: #53605C; background: transparent; font-size: 20px; font-weight: 500; }
        QPushButton#NavButton:hover { background: #EAF3F0; color: #26322F; }
        QPushButton#NavButton:checked { background: #E1F0EB; color: #176B5B; font-weight: 600; }
        QLabel#SyncStatus { color: #7B8984; font-size: 11px; padding: 0 4px; }
        QWidget#ContentCanvas, QScrollArea#DashboardScroll, QScrollArea#DashboardScroll > QWidget > QWidget { background: #F6F8F7; border: 0; }
        QLabel#PageTitle { color: #17201E; font-size: 28px; font-weight: 600; }
        QLabel#SectionTitle { color: #17201E; font-size: 18px; font-weight: 600; }
        QLabel#ModuleTitle { color: #26322F; font-size: 16px; font-weight: 600; }
        QLabel#TaskTitle { color: #17201E; font-size: 15px; font-weight: 500; }
        QLabel#BodyText { color: #26322F; font-size: 14px; font-weight: 400; }
        QLabel#BodyMuted { color: #66736F; font-size: 13px; font-weight: 400; }
        QLabel#MetaText { color: #788580; font-size: 12px; font-weight: 400; }
        QLabel#Eyebrow { color: #66736F; font-size: 13px; font-weight: 500; }
        QLabel#MetricText { color: #176B5B; font-size: 22px; font-weight: 600; }
        QLabel#SummaryNumber { color: #17201E; font-size: 20px; font-weight: 600; }
        QLabel#StatusTag { color: #53605C; background: #F0F4F2; border-radius: 8px; padding: 4px 8px; font-size: 11px; }
        QLabel#StatusTag[state="in_progress"] { color: #176B5B; background: #E7F3EF; }
        QLabel#StatusTag[state="blocked"] { color: #A3591C; background: #FFF2E4; }
        QFrame#Card, QFrame#SummaryCard, QFrame#SettingsCard { background: #FFFFFF; border: 1px solid #DDE7E3; border-radius: 13px; }
        QFrame#Divider { background: #EDF2F0; border: 0; }
        QWidget#Transparent { background: transparent; }
        QLabel#SettingLabel { color: #26322F; font-size: 14px; font-weight: 500; }
        QFrame#SummaryCard { min-width: 110px; max-width: 140px; }
        QFrame#TaskCard { background: #FFFFFF; border: 1px solid #E3EBE8; border-radius: 10px; min-height: 66px; }
        QFrame#TaskCard:hover { border-color: #BFD5CE; background: #FCFEFD; }
        QFrame#EmptyState { background: #FFFFFF; border: 1px solid #DDE7E3; border-radius: 13px; }
        QPushButton { border: 0; border-radius: 9px; padding: 0 14px; min-height: 38px; font-size: 13px; font-weight: 500; }
        QPushButton#Primary { color: #FFFFFF; background: #176B5B; }
        QPushButton#Primary:hover { background: #125A4C; }
        QPushButton#Secondary { color: #29554B; background: #FFFFFF; border: 1px solid #D4E2DD; }
        QPushButton#Secondary:hover { background: #F3F8F6; border-color: #BFD2CB; }
        QPushButton#Tertiary { color: #176B5B; background: transparent; padding: 0 4px; min-height: 30px; }
        QPushButton#Tertiary:hover { background: #E7F3EF; }
        QPushButton#Danger { color: #B9473F; background: transparent; }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit { min-height: 38px; color: #17201E; background: #FFFFFF; border: 1px solid #D7E2DE; border-radius: 8px; padding: 0 10px; selection-background-color: #CFE6DE; }
        QTextEdit { padding: 9px 10px; }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus { border: 1px solid #176B5B; }
        QDialog { background: #F8FAF9; }
        QDialog QLabel { color: #53605C; font-size: 13px; font-weight: 500; }
        QListWidget { background: #FFFFFF; border: 1px solid #DDE7E3; border-radius: 13px; padding: 8px; outline: 0; }
        QListWidget::item { color: #26322F; border-bottom: 1px solid #EDF2F0; padding: 12px 14px; border-radius: 8px; }
        QListWidget::item:hover { background: #F4F8F6; }
        QListWidget::item:selected { color: #176B5B; background: #E7F3EF; }
        QCheckBox#DoneCircle::indicator { width: 18px; height: 18px; border: 1.5px solid #A9B9B4; border-radius: 9px; background: #FFFFFF; }
        QCheckBox#DoneCircle::indicator:checked { background: #176B5B; border-color: #176B5B; }
        QCheckBox { color: #26322F; spacing: 9px; }
        QCheckBox::indicator { width: 19px; height: 19px; border: 1px solid #B8C7C2; border-radius: 5px; background: #FFFFFF; }
        QCheckBox::indicator:hover { border-color: #176B5B; }
        QCheckBox::indicator:checked { background: #176B5B; border-color: #176B5B; }
        QScrollBar:vertical { width: 8px; background: transparent; }
        QScrollBar::handle:vertical { min-height: 32px; border-radius: 4px; background: #CDD8D4; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """
        return (stylesheet.replace("#F6F8F7",canvas).replace("#F1F6F4",sidebar).replace("font-size: 14px",f"font-size: {base}px").replace("font-size: 15px",f"font-size: {base+1}px").replace("font-size: 13px",f"font-size: {max(13,base-1)}px").replace("font-size: 12px",f"font-size: {max(12,base-2)}px").replace("font-size: 11px",f"font-size: {max(12,base-3)}px").replace("font-size: 28px",f"font-size: {max(30,base+14)}px").replace("min-height: 66px",f"min-height: {compact_height}px"))
    def build(self):
        root = QWidget(); self.setCentralWidget(root); layout = QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(210); side = QVBoxLayout(sidebar); side.setContentsMargins(16,22,16,18); side.setSpacing(4)
        brand_row = QHBoxLayout(); brand_row.setSpacing(10); logo = QLabel(); logo.setFixedSize(34,34); pixmap=QPixmap(resource_path("assets/yanxu-logo-1024.png")); logo.setPixmap(pixmap.scaled(34,34,Qt.KeepAspectRatio,Qt.SmoothTransformation)); brand_copy=QVBoxLayout(); brand_copy.setSpacing(1); brand=QLabel("研序 YanXu"); brand.setObjectName("BrandName"); sub=QLabel("Research · Learn · Progress"); sub.setObjectName("BrandTagline"); brand_copy.addWidget(brand); brand_copy.addWidget(sub); brand_row.addWidget(logo); brand_row.addLayout(brand_copy,1); side.addLayout(brand_row); side.addSpacing(22)
        self.buttons = {}; names = [("today","今日"),("tasks","任务"),("projects","项目"),("reviews","复习"),("inbox","Inbox"),("calendar","日历"),("weekly","回顾"),("settings","设置")]
        self.nav_group=QButtonGroup(self); self.nav_group.setExclusive(True)
        for key, name in names:
            b = NavButton(key,name); b.clicked.connect(lambda _, k=key: self.show_page(k)); side.addWidget(b); self.buttons[key] = b; self.nav_group.addButton(b)
        side.addStretch(); self.sync_label = QLabel("仅本机"); self.sync_label.setObjectName("SyncStatus"); self.sync_label.setWordWrap(True); side.addWidget(self.sync_label); sync = QPushButton("立即同步"); sync.setObjectName("Secondary"); sync.clicked.connect(self.refresh); side.addWidget(sync); layout.addWidget(sidebar)
        self.pages = QStackedWidget(); layout.addWidget(self.pages, 1); self.today_page=TodayPage(); self.today_page.setProperty("key","today"); self.pages.addWidget(self.today_page)
        for key, _ in names[1:]:
            if key == "settings": self.settings_page = SettingsPage(self); self.settings_page.setProperty("key", key); self.pages.addWidget(self.settings_page)
            else: self.pages.addWidget(self.page_widget(key))
        self.show_page("today")
    def page_widget(self, key):
        page = QWidget(); page.setObjectName("ContentCanvas"); page.setProperty("key", key); layout = QVBoxLayout(page); layout.setContentsMargins(32,28,32,32); layout.setSpacing(8); head = QHBoxLayout(); title = QLabel(); title.setObjectName("PageTitle"); head.addWidget(title); head.addStretch(); action = QPushButton(); action.setObjectName("Primary"); action.setFixedHeight(40); head.addWidget(action); layout.addLayout(head); intro = QLabel(); intro.setObjectName("BodyMuted"); intro.setWordWrap(True); layout.addWidget(intro); layout.addSpacing(12); listing = QListWidget(); listing.itemDoubleClicked.connect(lambda item, k=key: self.edit(k, item.data(Qt.UserRole))); layout.addWidget(listing, 1); page.title, page.intro, page.action, page.listing = title, intro, action, listing; return page
    def show_page(self, key):
        order = ["today","tasks","projects","reviews","inbox","calendar","weekly","settings"]; self.pages.setCurrentIndex(order.index(key)); self.buttons[key].setChecked(True); self.render(key)
    def api(self, table, query=""):
        return self.cloud.request("GET", f"/rest/v1/{table}?{query}")
    def load_cache(self):
        try:
            with open(CACHE, encoding="utf-8") as f: return json.load(f)
        except (OSError, json.JSONDecodeError): return {}
    def save_cache(self):
        os.makedirs(APP_DIR, exist_ok=True); temp=CACHE+".tmp"
        with open(temp,"w",encoding="utf-8") as f: json.dump(self.data,f,ensure_ascii=False,indent=2)
        os.replace(temp,CACHE)
    def set_sync_state(self, text, failed=False):
        self.sync_label.setText(text); self.sync_label.setStyleSheet("color:#8A9692" if failed else f"color:{GREEN}")
    def refresh(self):
        if not self.cloud.ok(): self.set_sync_state("仅本机 · 尚未登录", True); self.show_page("settings"); return
        self.set_sync_state("正在同步…")
        pending_error = self.flush_pending()
        if pending_error:
            self.sync_error = pending_error; self.set_sync_state(f"离线 · {len(self.data.get('_pending', []))} 项待同步", True); self.render(self.pages.currentWidget().property("key")); return
        if not self.space_id:
            rows, err = self.api("space_members", f"select=space_id&user_id=eq.{self.settings.get('supabase_user_id','')}&limit=1")
            if err or not rows:
                self.sync_error = err or "未找到空间"; self.set_sync_state("离线 · 使用本地缓存", True); self.render(self.pages.currentWidget().property("key")); return
            self.space_id = rows[0]["space_id"]; self.settings["supabase_space_id"] = self.space_id; save_settings(self.settings)
        sid = self.space_id; uid = self.settings.get("supabase_user_id", "")
        requests = {"tasks":f"select=*&space_id=eq.{sid}&deleted_at=is.null&order=updated_at.desc","projects":f"select=*&space_id=eq.{sid}&deleted_at=is.null&order=updated_at.desc","milestones":"select=*&deleted_at=is.null","reviews":f"select=*&owner_id=eq.{uid}&deleted_at=is.null&order=next_review_at","inbox":f"select=*&owner_id=eq.{uid}&deleted_at=is.null&order=created_at.desc","focus":f"select=*&owner_id=eq.{uid}&deleted_at=is.null&order=started_at.desc"}
        for name, query in requests.items():
            rows, err = self.api({"inbox":"inbox_items","focus":"focus_sessions"}.get(name,name),query)
            self.data[name] = rows or []
            if err:
                self.sync_error = err; self.set_sync_state("离线 · 使用本地缓存", True); self.render(self.pages.currentWidget().property("key")); return
        self.sync_error = ""; self.save_cache(); self.settings["last_sync_at"] = dt.datetime.now().isoformat(timespec="seconds"); save_settings(self.settings); self.set_sync_state("已同步 · " + dt.datetime.now().strftime("%H:%M")); self.render(self.pages.currentWidget().property("key"))
    def render(self, key):
        page = self.pages.currentWidget(); today = dt.date.today().isoformat(); tasks = self.data.get("tasks", []); projects = self.data.get("projects", []); uid = self.settings.get("supabase_user_id", "")
        if key == "today":
            self.today_page.render_dashboard(tasks, projects, self.data.get("reviews",[]), self.data.get("inbox",[]), lambda:self.create("tasks"), lambda task:self.edit_focus(task), lambda task:self.edit_task(task), self.show_page)
            return
        if key == "settings":
            self.settings_page.refresh_status(); return
        rows, action, title, intro = [], "", "", ""
        if key == "tasks": title, intro, action, rows = "任务", "短期、具体、可执行的行动。", "新建任务", tasks
        elif key == "projects": title, intro, action, rows = "项目", "目标、里程碑和永远清晰的下一步。", "新建项目", projects
        elif key == "reviews": title, intro, action, rows = "强化复习", "复习仅服务于需要巩固的知识。双击条目进行反馈。", "新建复习", self.data.get("reviews", [])
        elif key == "inbox": title, intro, action, rows = "Inbox", "先捕获，再整理；双击可转为任务。", "快速捕获", self.data.get("inbox", [])
        elif key == "calendar": title, intro, action, rows = "日历", "时间分布视图；任务仍在任务页管理。", "新建任务", sorted(tasks, key=lambda x:(x.get("start_date",""),x.get("start_time", "")))
        elif key == "weekly":
            minutes = sum(x.get("duration_minutes",0) for x in self.data.get("focus",[])); title, intro, action, rows = "周回顾", f"已完成 {len([x for x in tasks if x.get('status')=='completed'])} 项 · 专注 {minutes//60}h {minutes%60}m", "记录本周", projects
        page.title.setText(title); page.intro.setText(intro); page.action.setText(action)
        try: page.action.clicked.disconnect()
        except TypeError: pass
        page.action.clicked.connect(lambda: self.create(key)); page.listing.clear()
        for row in rows:
            item = QListWidgetItem(self.row_text(key,row)); item.setData(Qt.UserRole,row); item.setSizeHint(QSize(0,58)); page.listing.addItem(item)
    def row_text(self, key, row):
        if row.get("_goto") or row.get("_focus"): return row["title"]
        if key in ("tasks","today","calendar"): return f"[{row.get('status','pending')}] {row.get('title','')}  · {row.get('start_date','')} {row.get('start_time') or ''}"
        if key == "projects": return f"{row.get('name','')}  · {row.get('progress',0)}%  · 下一步：{row.get('next_action') or '未设置'}"
        if key == "reviews": return f"{row.get('title','')}  · 下次：{row.get('next_review_at','')[:16]}"
        return row.get("content") or row.get("title") or ""
    def create(self, key):
        if key in ("today","tasks","calendar"): self.edit("tasks", None)
        elif key == "projects": self.edit("projects", None)
        elif key == "reviews": self.edit("reviews", None)
        elif key == "inbox": self.edit("inbox", None)
        elif key == "weekly": self.edit("weekly", None)
        elif key == "settings": self.edit("settings", None)
    def edit(self, key, row):
        if row and row.get("_goto"): return self.show_page(row["_goto"])
        if row and row.get("_focus"): return self.edit_focus()
        if key in ("today","calendar"): key = "tasks"
        if key == "tasks": self.edit_task(row)
        elif key == "projects": self.edit_project(row)
        elif key == "reviews": self.edit_review(row)
        elif key == "inbox": self.edit_inbox(row)
        elif key == "weekly": self.edit_weekly()
        elif key == "settings": self.edit_settings()
    def dialog(self, title, fields):
        d = Editor(title, fields, self); return d if d.exec_() == QDialog.Accepted else None
    def upsert(self, table, value, row=None):
        path = f"/rest/v1/{table}" + (f"?id=eq.{row['id']}" if row else "")
        _data, err = self.cloud.request("PATCH" if row else "POST", path, value, "return=minimal")
        if err:
            self.local_upsert(table, value, row); self.sync_error = err; self.set_sync_state(f"已存本机 · {len(self.data.get('_pending', []))} 项待同步", True)
            QMessageBox.information(self,"已保存到本机","网络或 Supabase 暂时不可用，内容已安全保存到本机。\n恢复连接后点击同步即可上传。\n\n连接信息："+err); return True
        self.refresh(); return True
    def local_upsert(self, table, value, row=None):
        key = {"inbox_items":"inbox","focus_sessions":"focus"}.get(table, table); rows = self.data.setdefault(key, [])
        local = dict(row or {}); local.update(value); local.setdefault("id", str(uuid.uuid4())); local["_pending_sync"] = True; local["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        index = next((i for i,item in enumerate(rows) if item.get("id") == local["id"]), None)
        if index is None: rows.insert(0, local)
        else: rows[index] = local
        pending = self.data.setdefault("_pending", []); previous = next((op for op in pending if op.get("table")==table and op.get("id")==local["id"]), None); pending[:] = [op for op in pending if not (op.get("table")==table and op.get("id")==local["id"])]
        method = previous.get("method") if previous else ("PATCH" if row else "POST"); queued_value = dict(previous.get("value", {}) if previous else {}); queued_value.update(value)
        if method == "POST": queued_value["id"] = local["id"]
        pending.append({"table":table,"id":local["id"],"method":method,"value":queued_value}); self.save_cache(); self.render(self.pages.currentWidget().property("key"))
    def flush_pending(self):
        pending = list(self.data.get("_pending", []))
        for op in pending:
            path=f"/rest/v1/{op['table']}"+(f"?id=eq.{op['id']}" if op["method"]=="PATCH" else "")
            _data,err=self.cloud.request(op["method"],path,op["value"],"return=minimal")
            if err: return err
            self.data["_pending"].remove(op); self.save_cache()
        return ""
    def edit_task(self,row):
        pnames = ["不关联"] + [p.get("name") for p in self.data.get("projects",[]) if p.get("status")=="active"]
        existing_project = next((p.get("name") for p in self.data.get("projects",[]) if p.get("id") == (row or {}).get("project_id")), "不关联")
        repeat=(row or {}).get("repeat_rule") or {}; repeat_value=repeat.get("frequency","none")
        d=self.dialog("任务",[("title","任务是什么？","text",(row or {}).get("title")),("start_date","开始日期","date",(row or {}).get("start_date")),("end_date","目标完成日","date",(row or {}).get("end_date") or (row or {}).get("start_date")),("start_time","开始时刻","time",(row or {}).get("start_time")),("estimated_minutes","预计分钟","number",(row or {}).get("estimated_minutes")),("priority",("优先级",["low","normal","high","today"]),"choice",(row or {}).get("priority","normal")),("status",("状态",["pending","in_progress","waiting","blocked","completed","cancelled"]),"choice",(row or {}).get("status","pending")),("project",("项目",pnames),"choice",existing_project),("repeat",("重复",["none","daily","weekdays","weekly"]),"choice",repeat_value),("blocker_reason","阻塞原因","text",(row or {}).get("blocker_reason")),("description","备注","note",(row or {}).get("description"))])
        if not d:return
        start_time=d.value("start_time")
        if d.value("end_date") < d.value("start_date"): return self.message("目标完成日不能早于开始日期。")
        project=next((p.get("id") for p in self.data.get("projects",[]) if p.get("name")==d.value("project")),None)
        repeat_value=d.value("repeat")
        value={"space_id":self.space_id,"creator_id":(row or {}).get("creator_id",self.settings.get("supabase_user_id")),"title":d.value("title"),"start_date":d.value("start_date"),"end_date":d.value("end_date"),"start_time":start_time or None,"all_day":False,"status":d.value("status"),"priority":d.value("priority"),"project_id":project,"estimated_minutes":d.value("estimated_minutes") or None,"blocker_reason":d.value("blocker_reason"),"description":d.value("description"),"reminder_policy":(row or {}).get("reminder_policy",{}),"repeat_rule":{} if repeat_value=="none" else {"frequency":repeat_value}}
        self.upsert("tasks",value,row)

    def edit_focus(self, selected_task=None):
        task_names=["不关联任务"]+[x.get("title","") for x in self.data.get("tasks",[]) if x.get("status") not in ("completed","cancelled")]
        default_task=(selected_task or {}).get("title") or task_names[0]
        d=self.dialog("记录专注",[("task",("关联任务",task_names),"choice",default_task),("minutes","专注分钟","number",(selected_task or {}).get("estimated_minutes") or 25),("note","结束备注","note","")])
        if not d:return
        task=next((x for x in self.data.get("tasks",[]) if x.get("title")==d.value("task")),None); minutes=max(1,d.value("minutes")); ended=dt.datetime.now(); started=ended-dt.timedelta(minutes=minutes)
        if self.upsert("focus_sessions",{"space_id":self.space_id,"owner_id":self.settings.get("supabase_user_id"),"task_id":task.get("id") if task else None,"started_at":started.isoformat(),"ended_at":ended.isoformat(),"duration_minutes":minutes,"note":d.value("note")},None) and task:
            self.cloud.request("POST","/rest/v1/rpc/increment_task_actual_minutes",{"task_uuid":task.get("id"),"minutes_to_add":minutes})
    def edit_project(self,row):
        d=self.dialog("项目",[("name","项目名称","text",(row or {}).get("name")),("goal","目标","note",(row or {}).get("goal")),("next_action","下一步行动","text",(row or {}).get("next_action")),("progress","进度 %","number",(row or {}).get("progress")),("notes","备注","note",(row or {}).get("notes"))])
        if d:self.upsert("projects",{"space_id":self.space_id,"owner_id":(row or {}).get("owner_id",self.settings.get("supabase_user_id")),"name":d.value("name"),"goal":d.value("goal"),"next_action":d.value("next_action"),"progress":min(100,d.value("progress")),"notes":d.value("notes"),"status":(row or {}).get("status","active"),"visibility":"shared"},row)
    def edit_review(self,row):
        if row:
            reply=QMessageBox.question(self,"复习反馈","是否记得这项内容？选择 Yes = 记得，No = 模糊。")
            step=(row.get("current_step",0)+1) if reply==QMessageBox.Yes else max(0,row.get("current_step",0)-1); intervals=row.get("intervals") or [1,2,4,7,15,30]; next_at=dt.datetime.now()+dt.timedelta(days=intervals[min(step,len(intervals)-1)])
            return self.upsert("reviews",{"current_step":step,"last_rating":"remembered" if reply==QMessageBox.Yes else "vague","next_review_at":next_at.isoformat()},row)
        d=self.dialog("新建复习",[("title","复习内容","text",""),("note","提示或摘要","note","")]);
        if d:self.upsert("reviews",{"space_id":self.space_id,"owner_id":self.settings.get("supabase_user_id"),"title":d.value("title"),"note":d.value("note"),"next_review_at":dt.datetime.now().isoformat()},None)
    def edit_inbox(self,row):
        if row:
            self.upsert("tasks",{"space_id":self.space_id,"creator_id":self.settings.get("supabase_user_id"),"title":row.get("content",""),"description":"","start_date":dt.date.today().isoformat(),"end_date":dt.date.today().isoformat(),"all_day":True,"status":"pending","priority":"normal","reminder_policy":{}},None); self.upsert("inbox_items",{"status":"converted"},row); return
        d=self.dialog("快速捕获",[("content","想到什么先记下来","note","")]);
        if d:self.upsert("inbox_items",{"space_id":self.space_id,"owner_id":self.settings.get("supabase_user_id"),"content":d.value("content")},None)
    def edit_weekly(self):
        d=self.dialog("本周回顾",[("highlights","推进与下周三项重点","note","")]);
        if d:self.upsert("weekly_reviews",{"space_id":self.space_id,"owner_id":self.settings.get("supabase_user_id"),"period_start":dt.date.today().isoformat(),"highlights":d.value("highlights"),"next_priorities":[]},None)
    def edit_settings(self):
        d=self.dialog("同步与账户",[("url","Supabase URL","text",self.settings.get("supabase_url")),("key","Publishable key","note",self.settings.get("supabase_key")),("email","邮箱","text",self.settings.get("supabase_email")),("password","密码（填写后登录）","text","")])
        if not d:return
        url=d.value("url").strip().rstrip("/")
        if url and not url.startswith(("https://","http://")): url="https://"+url
        parsed=urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.hostname: return self.message("Supabase URL 格式不正确，应类似 https://项目编号.supabase.co")
        self.settings.update({"supabase_url":url,"supabase_key":d.value("key").strip(),"supabase_email":d.value("email").strip()}); self.cloud=Cloud(self.settings)
        if d.value("password"):
            err=self.cloud.sign_in(d.value("email"),d.value("password"));
            if err:return self.message("登录失败："+err)
        save_settings(self.settings); self.refresh()
    def apply_preferences(self):
        self.setStyleSheet(self.style()); self.render(self.pages.currentWidget().property("key"))

    def setup_notifications(self):
        enabled = bool(self.settings.get("notifications_enabled", True))
        if enabled and QSystemTrayIcon.isSystemTrayAvailable():
            if self.tray is None:
                self.tray = QSystemTrayIcon(QIcon(resource_path("assets/yanxu-logo-1024.png")), self); self.tray.setToolTip("研序 YanXu"); self.tray.show()
            if not hasattr(self, "reminder_timer"):
                self.reminder_timer = QTimer(self); self.reminder_timer.setInterval(30000); self.reminder_timer.timeout.connect(self.check_reminders); self.reminder_timer.start(); QTimer.singleShot(2500, self.check_reminders)
            else: self.reminder_timer.start()
        elif hasattr(self, "reminder_timer"):
            self.reminder_timer.stop()
            if self.tray: self.tray.hide()

    def check_reminders(self):
        if not self.settings.get("notifications_enabled", True) or not self.tray: return
        now = dt.datetime.now(); today = now.date().isoformat()
        if self.settings.get("daily_summary", True) and self.settings.get("daily_summary_seen") != today:
            active = [x for x in self.data.get("tasks", []) if x.get("start_date") == today and x.get("status") not in ("completed", "cancelled")]
            self.tray.showMessage("今日概览", f"今天有 {len(active)} 项安排。先推进最重要的一步。", QSystemTrayIcon.Information, 5000)
            self.settings["daily_summary_seen"] = today; save_settings(self.settings)
        if not self.settings.get("task_reminders", True): return
        default_lead = int(self.settings.get("reminder_minutes", 10))
        for task in self.data.get("tasks", []):
            if task.get("start_date") != today or task.get("status") in ("completed", "cancelled") or not task.get("start_time"): continue
            try: start = dt.datetime.combine(now.date(), dt.datetime.strptime(task["start_time"][:5], "%H:%M").time())
            except (ValueError, TypeError): continue
            policy = task.get("reminder_policy") or {}; lead = int(policy.get("minutes_before", default_lead)); notify_at = start - dt.timedelta(minutes=lead); key = f"{task.get('id') or task.get('title')}:{start.isoformat()}:{lead}"
            if key not in self.notified and notify_at <= now < notify_at + dt.timedelta(seconds=60):
                when = "现在开始" if lead == 0 else f"将在 {lead} 分钟后开始"
                self.tray.showMessage("任务提醒", f"{task.get('title', '未命名任务')} · {when}", QSystemTrayIcon.Information, 7000); self.notified.add(key)

    def check_updates(self, manual=False):
        base = self.settings.get("supabase_url", "").rstrip("/")
        manifest_url = self.settings.get("update_manifest_url") or os.environ.get("YANXU_UPDATE_MANIFEST_URL", "") or (base + "/storage/v1/object/public/yanxu-releases/manifest.json" if base else "")
        if not manifest_url:
            self.update_message = f"当前版本 v{APP_VERSION} · 更新服务待接入"
            if hasattr(self, "settings_page"): self.settings_page.refresh_status()
            if manual: QMessageBox.information(self, "系统更新", "请先在“账户与连接”中填写 Supabase Project URL。")
            return
        try:
            if not manifest_url.startswith("https://"): raise ValueError("版本清单必须使用 HTTPS")
            context = ssl.create_default_context()
            if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"): context.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
            request = urllib.request.Request(manifest_url, headers={"Cache-Control": "no-cache", "User-Agent": "YanXu-Desktop/" + APP_VERSION})
            with urllib.request.urlopen(request, timeout=12, context=context) as response: manifest = json.loads(response.read().decode("utf-8"))
            latest = str(manifest.get("version") or "")
            channel = self.settings.get("update_channel", "stable")
            if hasattr(self, "settings_page"): channel = self.settings_page.update_channel.currentData()
            package = manifest.get("desktop") or {}; package_url = str(package.get("url") or ""); digest = str(package.get("sha256") or "").lower()
            if not re.fullmatch(r"\d+\.\d+\.\d+", latest): raise ValueError("版本号格式无效")
            if manifest.get("channel") not in ("stable", "preview"): raise ValueError("更新通道无效")
            if channel == "stable" and manifest.get("channel") != "stable":
                self.available_update = None; self.update_message = f"稳定版通道暂无更新 · v{APP_VERSION}"
            elif self._version_tuple(latest) > self._version_tuple(APP_VERSION):
                if not package_url.startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", digest): raise ValueError("Windows 下载地址或 SHA-256 无效")
                self.available_update = dict(manifest)
                self.update_message = f"发现新版本 v{latest}"
                if manual:
                    answer = QMessageBox.question(self, "发现新版本", f"研序 v{latest} 已发布。\n\n{manifest.get('release_notes') or '暂无更新说明'}\n\n现在下载更新吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if answer == QMessageBox.Yes: QTimer.singleShot(0, self.download_update)
            else:
                self.available_update = None
                self.update_message = f"已是最新版本 v{APP_VERSION}"
                if manual: QMessageBox.information(self, "系统更新", self.update_message)
        except Exception as exc:
            self.update_message = "更新检查失败"
            if manual: self.message("无法检查更新：" + str(exc))
        if hasattr(self, "settings_page"): self.settings_page.refresh_status()

    @staticmethod
    def _version_tuple(value):
        return tuple(int(part) for part in str(value).lstrip("v").split("."))

    def download_update(self):
        manifest = self.available_update
        if not manifest: return self.message("请先检查更新。")
        if not getattr(sys, "frozen", False): return self.message("源码运行模式不能自动替换程序，请使用发布版测试更新。")
        package = manifest["desktop"]; version = manifest["version"]
        os.makedirs(APP_DIR, exist_ok=True)
        partial = os.path.join(APP_DIR, f"YanXu-{version}-windows.zip.part")
        archive = os.path.join(APP_DIR, f"YanXu-{version}-windows.zip")
        progress = QProgressDialog("正在下载更新…", "取消", 0, 100, self); progress.setWindowTitle("研序更新"); progress.setMinimumDuration(0); progress.setWindowModality(Qt.WindowModal)
        try:
            request = urllib.request.Request(package["url"], headers={"User-Agent": "YanXu-Desktop/" + APP_VERSION})
            digest = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context()) as response, open(partial, "wb") as output:
                total = int(response.headers.get("Content-Length") or 0); received = 0
                if not total: progress.setRange(0, 0)
                while True:
                    block = response.read(65536)
                    if not block: break
                    output.write(block); digest.update(block); received += len(block)
                    if total: progress.setValue(min(99, int(received * 100 / total)))
                    QApplication.processEvents()
                    if progress.wasCanceled(): raise RuntimeError("下载已取消")
            if digest.hexdigest().lower() != package["sha256"].lower(): raise ValueError("SHA-256 校验失败，下载文件已丢弃")
            os.replace(partial, archive); progress.setLabelText("校验成功，正在准备更新…"); progress.setRange(0, 0); QApplication.processEvents()
            current_dir = os.path.dirname(sys.executable); parent = os.path.dirname(current_dir)
            stage = os.path.join(parent, ".YanXu-update-" + uuid.uuid4().hex); os.makedirs(stage)
            with zipfile.ZipFile(archive) as bundle:
                root = os.path.abspath(stage)
                for entry in bundle.infolist():
                    target = os.path.abspath(os.path.join(root, entry.filename))
                    if os.path.commonpath([root, target]) != root: raise ValueError("更新包包含不安全路径")
                bundle.extractall(stage)
            if not os.path.isfile(os.path.join(stage, "YanXu.exe")): raise ValueError("更新包缺少 YanXu.exe")
            backup = os.path.join(parent, f"YanXu.rollback-{APP_VERSION}-{dt.datetime.now():%Y%m%d-%H%M%S}")
            script = self._write_updater_script()
            answer = QMessageBox.question(self, "更新已就绪", "下载与 SHA-256 校验成功。\n\n现在重启并完成更新吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer != QMessageBox.Yes: self.update_message = f"v{version} 已下载 · 重启后可再次安装"; return
            subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, str(os.getpid()), current_dir, stage, backup, "YanXu.exe"], close_fds=True)
            QApplication.quit()
        except Exception as exc:
            try:
                if os.path.isfile(partial): os.remove(partial)
            except OSError: pass
            self.message("更新未安装，当前版本保持不变。\n\n" + str(exc))
        finally:
            progress.close()

    @staticmethod
    def _write_updater_script():
        script_path = os.path.join(tempfile.gettempdir(), "YanXu-updater-" + uuid.uuid4().hex + ".ps1")
        source = r'''param([int]$ProcessId,[string]$CurrentDir,[string]$StagedDir,[string]$BackupDir,[string]$ExeName)
$ErrorActionPreference = 'Stop'
try { Wait-Process -Id $ProcessId -Timeout 60 -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 800
$movedCurrent = $false
try {
    if (Test-Path -LiteralPath $CurrentDir) { Move-Item -LiteralPath $CurrentDir -Destination $BackupDir; $movedCurrent = $true }
    Move-Item -LiteralPath $StagedDir -Destination $CurrentDir
    Start-Process -FilePath (Join-Path $CurrentDir $ExeName)
} catch {
    if (-not (Test-Path -LiteralPath $CurrentDir) -and $movedCurrent -and (Test-Path -LiteralPath $BackupDir)) { Move-Item -LiteralPath $BackupDir -Destination $CurrentDir }
    if (Test-Path -LiteralPath (Join-Path $CurrentDir $ExeName)) { Start-Process -FilePath (Join-Path $CurrentDir $ExeName) }
}
'''
        with open(script_path, "w", encoding="utf-8-sig", newline="\r\n") as handle: handle.write(source)
        return script_path
    def message(self,text): QMessageBox.warning(self,"研序 YanXu",text)


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True); QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    application=QApplication([]); application.setApplicationName("研序 YanXu"); window=YanXu(); window.show(); application.exec_()
