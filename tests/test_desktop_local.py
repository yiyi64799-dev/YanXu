import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from PyQt5.QtTest import QTest
from yanxu_store import LocalStore
from yanxu_desktop import DesktopWindow, TaskEditor


class TestDirectory:
    """Retain test fixtures; project policy prohibits recursive cleanup."""
    def __init__(self):
        root=Path(__file__).resolve().parents[1]/'artifacts'/'desktop-test-data'
        root.mkdir(parents=True,exist_ok=True)
        self.name=tempfile.mkdtemp(prefix='test-',dir=str(root))
    def __enter__(self):return self.name
    def __exit__(self,*args):pass
    def cleanup(self):pass


class StorageTests(unittest.TestCase):
    def test_migration_preserves_original_and_pending(self):
        with TestDirectory() as temp:
            cache=Path(temp)/'v2-cache.json'
            legacy={'tasks':[{'id':'old','title':'原任务','status':'pending'}], '_pending':[{'id':'old'}]}
            cache.write_text(json.dumps(legacy),encoding='utf-8')
            original=cache.read_bytes()
            store=LocalStore(temp)
            self.assertEqual(store.load()['tasks'][0]['title'],'原任务')
            store.upsert('tasks',{'title':'已编辑'},store.load()['tasks'][0])
            store.close()
            again=LocalStore(temp)
            self.assertEqual(again.load()['tasks'][0]['title'],'已编辑')
            self.assertEqual(cache.read_bytes(),original)
            self.assertTrue(list((Path(temp)/'backups').glob('legacy-cache-*.json')))
            self.assertEqual(json.loads(again.db.execute("SELECT value FROM metadata WHERE key='legacy_pending'").fetchone()[0]),legacy['_pending'])
            again.close()

    def test_export_restore_and_soft_delete(self):
        with TestDirectory() as temp:
            store=LocalStore(temp)
            task=store.upsert('tasks',{'title':'任务'})
            export=Path(temp)/'export.json'
            store.export(export)
            store.upsert('tasks',{'deleted_at':'2026-09-20'},task)
            self.assertEqual(store.load()['tasks'],[])
            store.restore(export)
            self.assertEqual(store.load()['tasks'][0]['title'],'任务')
            self.assertTrue(list((Path(temp)/'backups').glob('before-restore-*.sqlite3')))
            store.close()

    def test_invalid_restore_does_not_destroy_data(self):
        with TestDirectory() as temp:
            store=LocalStore(temp)
            store.upsert('tasks',{'title':'保留'})
            bad=Path(temp)/'invalid.json'
            bad.write_text('{"_format":"yanxu-desktop-1","tasks":[1]}',encoding='utf-8')
            with self.assertRaises(ValueError):store.restore(bad)
            self.assertEqual(store.load()['tasks'][0]['title'],'保留')
            store.close()


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setFont(QFont('Microsoft YaHei UI',11))

    def setUp(self):
        self.temp=TestDirectory()
        self.network=patch('yanxu_v2_app.Cloud.request',side_effect=AssertionError('Local desktop must not access cloud'))
        self.network.start()
        self.window=DesktopWindow(self.temp.name)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.network.stop()
        self.temp.cleanup()

    def test_offline_create_complete_undo_reload(self):
        day=dt.date.today().isoformat()
        self.assertTrue(self.window.upsert('tasks',{'title':'离线任务','start_date':day,'end_date':day,'status':'pending'}))
        task=self.window.data['tasks'][0]
        self.window.complete_task(task,True)
        self.assertEqual(self.window.data['tasks'][0]['status'],'completed')
        self.window.undo()
        self.assertEqual(self.window.data['tasks'][0]['status'],'pending')
        self.window.refresh()
        self.assertEqual(self.window.data['tasks'][0]['title'],'离线任务')

    def test_pages_and_editor_validation(self):
        for page in self.window.buttons:
            self.window.show_page(page)
            self.app.processEvents()
        dialog=TaskEditor(self.window)
        dialog.validate()
        self.assertIn('名称',dialog.error.text())
        dialog.title.setText('有效任务')
        dialog.end.setDate(QDate(2000,1,1))
        dialog.validate()
        self.assertIn('不能早于',dialog.error.text())
        dialog.end.setDate(dialog.start.date())
        dialog.validate()
        self.assertEqual(dialog.result(),1)
        self.assertIsNone(dialog.value()['start_time'])
        dialog.deleteLater()

    def test_focus_pause_and_save(self):
        self.window.start_focus()
        self.window.focus_elapsed=65
        self.window.toggle_focus()
        self.assertIsNone(self.window.focus_started)
        self.assertTrue(self.window.finish_focus())
        self.assertGreaterEqual(self.window.data['focus'][0]['duration_seconds'],65)

    def test_preview_screens_and_geometry(self):
        today=dt.date.today().isoformat()
        project=self.window.store.upsert('projects',{'name':'论文实验','next_action':'确认对照组配置','status':'active'})
        for title,priority in [('整理消融实验结果','today'),('写完组会汇报提纲','today'),('阅读一篇相关工作','normal')]:
            self.window.store.upsert('tasks',{'title':title,'priority':priority,'start_date':today,'end_date':today,'status':'pending','project_id':project['id'],'estimated_minutes':45})
        self.window.refresh()
        for width,height in [(1160,760),(940,650)]:
            self.window.resize(width,height)
            self.app.processEvents()
            self.assertLessEqual(self.window.minimumSizeHint().width(),1160)
        shots=Path(__file__).resolve().parents[1]/'artifacts'/'desktop-preview-qa'
        shots.mkdir(parents=True,exist_ok=True)
        scale=os.environ.get('QT_SCALE_FACTOR','1')
        self.window.resize(1160,760)
        self.app.processEvents()
        self.window.grab().save(str(shots/f'today-{scale}.png'))
        dialog=TaskEditor(self.window)
        dialog.show()
        self.app.processEvents()
        dialog.grab().save(str(shots/f'new-task-{scale}.png'))
        dialog.close()
        self.window.show_detail(self.window.data['tasks'][0])
        QTest.qWait(150)
        self.window.repaint()
        self.window.detail.grab().save(str(shots/f'detail-{scale}.png'))
        self.assertTrue(self.window.detail.isVisible())
        self.window.detail.hide()
        dialog=TaskEditor(self.window)
        dialog.show()
        dialog.expand(True)
        QTest.qWait(50)
        self.assertLessEqual(dialog.height(),self.app.primaryScreen().availableGeometry().height())
        dialog.grab().save(str(shots/f'new-task-expanded-{scale}.png'))
        dialog.close()

    def test_reminder_fires_once_without_network(self):
        now=dt.datetime.now()
        self.window.store.upsert('tasks',{'title':'提醒测试','start_date':now.date().isoformat(),'start_time':now.strftime('%H:%M'),'reminder_policy':{'enabled':True,'minutes_before':0}})
        self.window.data=self.window.store.load()
        from unittest.mock import Mock
        original=self.window.tray
        fake=Mock()
        self.window.tray=fake
        self.window.check_reminders()
        self.window.check_reminders()
        self.assertEqual(fake.showMessage.call_count,1)
        self.window.tray=original

    def test_reopen_retains_task(self):
        self.window.upsert('tasks',{'title':'重启保留','status':'pending'})
        self.window.close()
        self.window=DesktopWindow(self.temp.name)
        self.assertEqual(self.window.data['tasks'][0]['title'],'重启保留')

    def test_long_title_detail_does_not_squeeze_home(self):
        text=('检查代码，兼容单卡和多卡。\n优化方案，保留实验细节。\n'*30)+'<保留原文>'
        self.window.store.upsert('tasks',{'title':text,'status':'completed','description':'完整备注'})
        self.window.refresh()
        self.app.processEvents()
        before=self.window.centralWidget().geometry()
        task=self.window.data['tasks'][0]
        self.window.show_detail(task)
        QTest.qWait(80)
        self.assertEqual(before,self.window.centralWidget().geometry())
        self.assertLessEqual(self.window.detail.width(),680)
        dialog=TaskEditor(self.window,task)
        self.assertEqual(dialog.value()['title'],text)
        self.window.detail.close()
        dialog.close()

    def test_project_goal_and_equal_navigation(self):
        self.window.store.upsert('projects',{'name':'测试项目','goal':'验证真实项目目标可见','next_action':'完成测试'})
        self.window.data=self.window.store.load()
        self.window.show_page('projects')
        self.app.processEvents()
        from PyQt5.QtWidgets import QLabel
        self.assertIn('验证真实项目目标可见',[w.text() for w in self.window.findChildren(QLabel)])
        self.assertEqual(len({b.height() for b in self.window.buttons.values()}),1)
        self.assertEqual(len({b.font().pixelSize() for b in self.window.buttons.values()}),1)

    def test_knowledge_feedback_persists_and_legacy_is_retained(self):
        self.window.store.upsert('reviews',{'title':'为什么需要对照实验？','note':'排除其他因素','id':'review-example'})
        self.window.refresh()
        self.window.show_page('reviews')
        row=self.window.data['reviews'][0]
        self.window.rate_knowledge(row,False)
        updated=self.window.data['reviews'][0]
        self.assertEqual(updated['note'],'排除其他因素')
        self.assertEqual(updated['last_rating'],'vague')
        self.assertGreater(updated['next_review_at'],dt.datetime.now().isoformat())

    def test_feature_screens_and_answer_reveal(self):
        today=dt.date.today().isoformat()
        project=self.window.store.upsert('projects',{'name':'论文实验','goal':'用可复现的对照实验验证方案效果，并整理实验报告。','next_action':'确认对照组配置','status':'active'})
        self.window.store.upsert('tasks',{'title':'整理实验结果\n对比单卡与多卡运行情况，检查配置与日志，记录差异。'*4,'status':'completed','completed_at':dt.datetime.now().isoformat(),'start_date':today,'end_date':today,'project_id':project['id']})
        self.window.store.upsert('reviews',{'title':'消融实验和对照实验分别回答什么问题？','note':'消融实验考察某个组成部分的贡献；对照实验在其他条件一致时比较目标因素。','source':'方法阅读笔记','project_id':project['id']})
        self.window.store.upsert('focus',{'ended_at':dt.datetime.now().isoformat(),'duration_minutes':45})
        self.window.store.upsert('weekly_reviews',{'period_start':today,'highlights':'确认了实验设置中的一个变量。','next_plan':'先跑一组小规模验证。'})
        self.window.data=self.window.store.load()
        shots=Path(__file__).resolve().parents[1]/'artifacts'/'desktop-polish-qa'
        shots.mkdir(parents=True,exist_ok=True)
        scale=os.environ.get('QT_SCALE_FACTOR','1')
        from PyQt5.QtWidgets import QPushButton
        from PyQt5.QtCore import Qt
        self.window.resize(1060,720)
        for page in ['today','projects','reviews','weekly']:
            self.window.show_page(page)
            QTest.qWait(60)
            if page=='reviews':
                reveal=next(b for b in self.window.findChildren(QPushButton) if b.text()=='查看答案' and b.isVisible())
                QTest.mouseClick(reveal,Qt.LeftButton)
                self.assertEqual(reveal.text(),'收起答案')
            self.window.grab().save(str(shots/f'{page}-{scale}.png'))
        self.window.show_page('today')
        before=self.window.centralWidget().geometry()
        self.window.show_detail(self.window.data['tasks'][0])
        QTest.qWait(60)
        self.assertEqual(before,self.window.centralWidget().geometry())
        self.window.detail.grab().save(str(shots/f'long-detail-{scale}.png'))
        self.window.detail.hide()


if __name__=='__main__':unittest.main()
