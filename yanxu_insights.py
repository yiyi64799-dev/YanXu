"""Deterministic summaries and review scheduling based on existing local records."""
import datetime as dt


def local_date(value):
    if not value:return None
    try:
        date=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return date.astimezone().date() if date.tzinfo else date.date()
    except (ValueError,TypeError):return None


def week_summary(data,today=None):
    today=today or dt.date.today()
    start=today-dt.timedelta(days=today.weekday())
    days=[{'date':start+dt.timedelta(days=i),'tasks':0,'seconds':0} for i in range(7)]
    completed=[]
    project_ids=set()
    for task in data.get('tasks',[]):
        day=local_date(task.get('completed_at'))
        if task.get('status')=='completed' and day and start<=day<=today:
            days[(day-start).days]['tasks']+=1
            completed.append(task)
            if task.get('project_id'):project_ids.add(task['project_id'])
    for session in data.get('focus',[]):
        day=local_date(session.get('ended_at'))
        if day and start<=day<=today:
            seconds=session.get('duration_seconds')
            if seconds is None:seconds=(session.get('duration_minutes') or 0)*60
            try:seconds=max(0,int(seconds))
            except (TypeError,ValueError):seconds=0
            days[(day-start).days]['seconds']+=seconds
    return {'start':start,'today':today,'days':days,'completed':completed,
            'minutes':sum(d['seconds'] for d in days)//60,'project_count':len(project_ids)}


def starter_task(tasks,budget=15,today=None):
    day=(today or dt.date.today()).isoformat()
    eligible=[]
    for task in tasks:
        if task.get('status','pending') not in ('pending','in_progress'):continue
        if (task.get('start_date') or day)>day:continue
        try:minutes=int(task.get('estimated_minutes') or 0)
        except (TypeError,ValueError):continue
        if 0<minutes<=budget:eligible.append(task)
    return min(eligible,key=lambda t:(t.get('end_date') or '9999',int(t['estimated_minutes']),t.get('id',''))) if eligible else None


def review_due(row,now=None):
    if not row.get('is_active',True):return False
    value=row.get('next_review_at')
    if not value:return True
    try:
        when=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if when.tzinfo:when=when.astimezone().replace(tzinfo=None)
        return when <= (now or dt.datetime.now())
    except (ValueError,TypeError):return True


def review_feedback(row,remembered,now=None):
    now=now or dt.datetime.now()
    intervals=[1,2,4,7,15,30]
    step=min(5,max(0,int(row.get('current_step') or 0))+1) if remembered else 0
    return {'current_step':step,'last_rating':'remembered' if remembered else 'vague',
            'last_reviewed_at':now.isoformat(timespec='seconds'),
            'next_review_at':(now+dt.timedelta(days=intervals[step])).isoformat(timespec='seconds')}


def week_report(data,today=None):
    summary=week_summary(data,today)
    lines=[f"本周进展 · {summary['start']} 至 {summary['today']}",
           f"完成 {len(summary['completed'])} 项任务 · 专注 {summary['minutes']} 分钟 · 推进 {summary['project_count']} 个项目",'', '完成事项：']
    lines.extend('- '+t.get('title','未命名任务') for t in summary['completed'])
    if not summary['completed']:lines.append('暂无本周完成记录。')
    notes=[n for n in data.get('weekly_reviews',[]) if summary['start'].isoformat()<=(n.get('period_start') or '')<=summary['today'].isoformat()]
    for note in notes:
        lines.extend(['','本周心得：',note.get('highlights') or '未填写','下一步：',note.get('next_plan') or '未填写'])
    return '\n'.join(lines)
