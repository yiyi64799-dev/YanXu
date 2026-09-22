import datetime as dt
import unittest
from yanxu_insights import week_summary,week_report,starter_task,review_due,review_feedback


class InsightsTests(unittest.TestCase):
    def test_week_boundaries_and_missing_completion_time(self):
        data={'tasks':[{'title':'本周','status':'completed','completed_at':'2026-09-22T12:00:00','project_id':'p'},
                       {'title':'上周','status':'completed','completed_at':'2026-09-20T12:00:00'},
                       {'title':'无完成时间','status':'completed'},
                       {'title':'未来','status':'completed','completed_at':'2026-09-23T12:00:00'}],
              'focus':[{'ended_at':'2026-09-22T13:00:00','duration_seconds':125},
                       {'ended_at':'2026-09-21T13:00:00','duration_minutes':5},
                       {'ended_at':'2026-09-20T13:00:00','duration_minutes':999}]}
        report=week_summary(data,dt.date(2026,9,22))
        self.assertEqual(report['start'],dt.date(2026,9,21))
        self.assertEqual(len(report['completed']),1)
        self.assertEqual(report['minutes'],7)
        self.assertEqual(report['project_count'],1)
        self.assertIn('本周',week_report(data,dt.date(2026,9,22)))

    def test_starter_excludes_blocked_future_and_unknown_duration(self):
        tasks=[{'id':'a','status':'blocked','estimated_minutes':5},
               {'id':'b','status':'pending','estimated_minutes':10,'start_date':'2027-01-01'},
               {'id':'c','status':'completed','estimated_minutes':1},
               {'id':'d','status':'pending'},
               {'id':'e','status':'pending','estimated_minutes':15},
               {'id':'f','status':'pending','estimated_minutes':30}]
        self.assertEqual(starter_task(tasks,today=dt.date(2026,9,22))['id'],'e')
        self.assertIsNone(starter_task(tasks,budget=5,today=dt.date(2026,9,22)))

    def test_review_scheduling(self):
        now=dt.datetime(2026,9,22,12)
        next_values=review_feedback({'current_step':0},True,now)
        self.assertEqual(next_values['next_review_at'],'2026-09-24T12:00:00')
        reset=review_feedback({'current_step':5},False,now)
        self.assertEqual(reset['next_review_at'],'2026-09-23T12:00:00')
        self.assertFalse(review_due(next_values,now))
        self.assertTrue(review_due({},now))
        self.assertFalse(review_due({'is_active':False},now))


if __name__=='__main__':unittest.main()
