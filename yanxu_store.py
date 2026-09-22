"""Transactional desktop storage. Never changes the legacy cloud cache or credentials."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

TABLES = ('tasks', 'projects', 'milestones', 'reviews', 'inbox', 'focus', 'weekly_reviews')
ALIASES = {'inbox_items': 'inbox', 'focus_sessions': 'focus'}


class LocalStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'desktop.sqlite3'
        self.db = sqlite3.connect(str(self.path))
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id)); CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);')
        self.import_legacy()
        daily = self.directory / 'backups' / ('desktop-' + dt.date.today().isoformat() + '.sqlite3')
        if not daily.exists():
            self.backup(daily)

    def import_legacy(self):
        if self.db.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
            return
        legacy = self.directory / 'v2-cache.json'
        data = {}
        if legacy.exists():
            # Parse before recording success; malformed caches must never be silently ignored.
            data = json.loads(legacy.read_text(encoding='utf-8'))
            self.validate(data)
            backup = self.directory / 'backups' / ('legacy-cache-' + uuid.uuid4().hex + '.json')
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, backup)
        with self.db:
            for kind in TABLES:
                for row in data.get(kind, []):
                    value = dict(row)
                    value.setdefault('id', str(uuid.uuid4()))
                    self.db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?)', (kind, value['id'], json.dumps(value, ensure_ascii=False)))
            # Preserve queue for a future explicit cloud migration, never upload it implicitly.
            self.db.execute('INSERT INTO metadata VALUES (?,?)', ('legacy_pending', json.dumps(data.get('_pending', []))))
            self.db.execute('INSERT INTO metadata VALUES (?,?)', ('legacy_imported', dt.datetime.now().isoformat()))

    @staticmethod
    def validate(data):
        if not isinstance(data, dict):
            raise ValueError('备份格式不正确：应为数据对象。')
        for kind in TABLES:
            rows = data.get(kind, [])
            if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
                raise ValueError('备份中的 %s 格式不正确。' % kind)
            ids = [x.get('id') for x in rows if x.get('id') is not None]
            if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
                raise ValueError('备份含无效或重复的记录编号。')

    def load(self):
        data = {kind: [] for kind in TABLES}
        for kind, payload in self.db.execute('SELECT kind,payload FROM records ORDER BY rowid DESC'):
            value = json.loads(payload)
            if not value.get('deleted_at'):
                data[kind].append(value)
        return data

    def upsert(self, table, value, row=None):
        kind = ALIASES.get(table, table)
        if kind not in TABLES:
            raise ValueError('未知记录类型')
        record = dict(row or {})
        record.update(value)
        record.setdefault('id', str(uuid.uuid4()))
        record.setdefault('created_at', dt.datetime.now().isoformat(timespec='seconds'))
        record['updated_at'] = dt.datetime.now().isoformat(timespec='seconds')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (kind, record['id'], json.dumps(record, ensure_ascii=False)))
        return record

    def backup(self, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(path))
        try:
            self.db.backup(target)
        finally:
            target.close()
        return path

    def export(self, destination):
        # Export business data only; no account settings, tokens or signing material.
        data = {kind: [] for kind in TABLES}
        for kind, payload in self.db.execute('SELECT kind,payload FROM records'):
            data[kind].append(json.loads(payload))
        data['_format'] = 'yanxu-desktop-1'
        path = Path(destination)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)

    def restore(self, source):
        data = json.loads(Path(source).read_text(encoding='utf-8'))
        self.validate(data)
        if data.get('_format') != 'yanxu-desktop-1':
            raise ValueError('请选择研序桌面版导出的备份。')
        self.backup(self.directory / 'backups' / ('before-restore-' + uuid.uuid4().hex + '.sqlite3'))
        with self.db:
            self.db.execute('DELETE FROM records')
            for kind in TABLES:
                for row in data.get(kind, []):
                    value = dict(row)
                    value.setdefault('id', str(uuid.uuid4()))
                    self.db.execute('INSERT INTO records VALUES (?,?,?)', (kind, value['id'], json.dumps(value, ensure_ascii=False)))

    def close(self):
        self.db.close()
