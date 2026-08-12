import './style.css'
import { createClient, type RealtimeChannel, type Session, type SupabaseClient } from '@supabase/supabase-js'
import { Capacitor } from '@capacitor/core'
import { LocalNotifications } from '@capacitor/local-notifications'
import { bootYanXu } from './v2'

type AppConfig = { url: string; key: string }
type Member = { user_id: string; role: string; display_name: string }
type Space = { id: string; name: string; invite_code: string }
type Task = {
  id: string
  space_id: string
  creator_id: string
  assignee_id: string | null
  title: string
  description: string
  start_date: string
  end_date: string
  start_time: string | null
  end_time: string | null
  all_day: boolean
  reminder_at: string | null
}
type DayStatus = { task_id: string; user_id: string; task_date: string; status: string }

const root = document.querySelector<HTMLDivElement>('#app')!
let config = loadConfig()
let supabase: SupabaseClient | null = null
let session: Session | null = null
let space: Space | null = null
let members: Member[] = []
let tasks: Task[] = []
let statuses: DayStatus[] = []
let selectedDate = isoDate(new Date())
let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
let realtimeChannel: RealtimeChannel | null = null
let editingTask: Task | null = null

function loadConfig(): AppConfig | null {
  try {
    const saved = JSON.parse(localStorage.getItem('focus-supabase') || 'null')
    return saved?.url && saved?.key ? saved : null
  } catch {
    return null
  }
}

function isoDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function esc(value: unknown) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function formatDay(value: string) {
  const date = parseDate(value)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

function setError(message = '') {
  const element = document.querySelector<HTMLElement>('[data-error]')
  if (element) {
    element.textContent = message
    element.hidden = !message
  }
}

function initClient() {
  if (!config) return
  supabase = createClient(config.url, config.key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false }
  })
  supabase.auth.onAuthStateChange((_event, nextSession) => {
    session = nextSession
    void route()
  })
}

async function route() {
  if (!config || !supabase) {
    renderConfig()
    return
  }
  const result = await supabase.auth.getSession()
  session = result.data.session
  if (!session) {
    renderAuth()
    return
  }
  await loadSpace()
  if (!space) {
    renderSpaceSetup()
    return
  }
  await loadCalendarData()
  subscribeRealtime()
  renderApp()
}

function renderConfig() {
  root.innerHTML = `
    <main class="screen-center">
      <section class="auth-card">
        <div class="brand-kicker">Focus Calendar</div>
        <h1>连接你们的日历</h1>
        <p>填写 Supabase 项目设置。发布密钥会保存在这台手机本地，数据权限由数据库的 RLS 规则保护。</p>
        <div class="error" data-error hidden></div>
        <form id="config-form">
          <div class="field"><label>Project URL</label><input name="url" type="url" required placeholder="https://xxxx.supabase.co" /></div>
          <div class="field"><label>Publishable / anon key</label><textarea name="key" required placeholder="sb_publishable_... 或 eyJ..."></textarea></div>
          <button class="primary wide" type="submit">保存并连接</button>
        </form>
      </section>
    </main>`
  document.querySelector<HTMLFormElement>('#config-form')!.addEventListener('submit', (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget as HTMLFormElement)
    const url = String(form.get('url') || '').trim().replace(/\/$/, '')
    const key = String(form.get('key') || '').trim()
    if (!url.includes('.supabase.co') || key.length < 20) {
      setError('项目地址或发布密钥格式不正确。')
      return
    }
    config = { url, key }
    localStorage.setItem('focus-supabase', JSON.stringify(config))
    initClient()
    void route()
  })
}

function renderAuth() {
  root.innerHTML = `
    <main class="screen-center">
      <section class="auth-card">
        <div class="brand-kicker">Two people · One rhythm</div>
        <h1>欢迎回来</h1>
        <p>你们各自登录自己的账号。安排互相可见，但每天的完成状态只属于自己。</p>
        <div class="error" data-error hidden></div>
        <form id="auth-form">
          <div class="field"><label>你的称呼</label><input name="name" autocomplete="name" placeholder="例如：小林" /></div>
          <div class="field"><label>邮箱</label><input name="email" type="email" autocomplete="email" required /></div>
          <div class="field"><label>密码</label><input name="password" type="password" minlength="6" autocomplete="current-password" required /></div>
          <div class="split">
            <button class="primary" name="action" value="login" type="submit">登录</button>
            <button class="secondary" name="action" value="signup" type="submit">注册</button>
          </div>
        </form>
        <div class="divider">连接设置</div>
        <button id="reset-config" class="secondary wide">更换 Supabase 项目</button>
      </section>
    </main>`
  document.querySelector<HTMLFormElement>('#auth-form')!.addEventListener('submit', async (event) => {
    event.preventDefault()
    if (!supabase) return
    setError()
    const submitter = (event as SubmitEvent).submitter as HTMLButtonElement
    const data = new FormData(event.currentTarget as HTMLFormElement)
    const email = String(data.get('email') || '').trim()
    const password = String(data.get('password') || '')
    const name = String(data.get('name') || '').trim()
    const response = submitter.value === 'signup'
      ? await supabase.auth.signUp({ email, password, options: { data: { display_name: name || email.split('@')[0] } } })
      : await supabase.auth.signInWithPassword({ email, password })
    if (response.error) setError(response.error.message)
    else if (submitter.value === 'signup' && !response.data.session) setError('注册成功，请先在邮箱中完成确认后再登录。')
  })
  document.querySelector('#reset-config')!.addEventListener('click', () => {
    localStorage.removeItem('focus-supabase')
    config = null
    supabase = null
    renderConfig()
  })
}

async function loadSpace() {
  if (!supabase || !session) return
  const { data } = await supabase
    .from('space_members')
    .select('space_id, role, spaces(id, name, invite_code)')
    .eq('user_id', session.user.id)
    .limit(1)
    .maybeSingle()
  const nested = data?.spaces as unknown as Space | null
  space = nested || null
}

function renderSpaceSetup() {
  root.innerHTML = `
    <main class="screen-center">
      <section class="auth-card">
        <div class="brand-kicker">Our Space</div>
        <h1>建立两个人的空间</h1>
        <p>第一位创建空间并把邀请码发给 TA；第二位输入邀请码加入。一个空间最多两位成员。</p>
        <div class="error" data-error hidden></div>
        <form id="create-space">
          <div class="field"><label>你的称呼</label><input name="name" required placeholder="我在日历中的名字" /></div>
          <div class="field"><label>空间名称</label><input name="space" value="我们的日历" required /></div>
          <button class="primary wide">创建情侣空间</button>
        </form>
        <div class="divider">或者</div>
        <form id="join-space">
          <div class="field"><label>你的称呼</label><input name="name" required placeholder="我在日历中的名字" /></div>
          <div class="field"><label>对方发来的邀请码</label><input name="code" required maxlength="8" placeholder="8 位邀请码" /></div>
          <button class="secondary wide">加入对方的空间</button>
        </form>
      </section>
    </main>`
  document.querySelector<HTMLFormElement>('#create-space')!.addEventListener('submit', async (event) => {
    event.preventDefault()
    if (!supabase) return
    const data = new FormData(event.currentTarget as HTMLFormElement)
    const response = await supabase.rpc('create_couple_space', {
      space_name: String(data.get('space') || ''), member_name: String(data.get('name') || '')
    })
    if (response.error) setError(response.error.message)
    else await route()
  })
  document.querySelector<HTMLFormElement>('#join-space')!.addEventListener('submit', async (event) => {
    event.preventDefault()
    if (!supabase) return
    const data = new FormData(event.currentTarget as HTMLFormElement)
    const response = await supabase.rpc('join_couple_space', {
      code: String(data.get('code') || ''), member_name: String(data.get('name') || '')
    })
    if (response.error) setError(response.error.message)
    else await route()
  })
}

async function loadCalendarData() {
  if (!supabase || !space || !session) return
  const monthStart = isoDate(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1))
  const monthEnd = isoDate(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0))
  const [memberResult, taskResult] = await Promise.all([
    supabase.from('space_members').select('user_id, role, profiles(display_name)').eq('space_id', space.id),
    supabase.from('tasks').select('*').eq('space_id', space.id).lte('start_date', monthEnd).gte('end_date', monthStart).order('start_date')
  ])
  members = (memberResult.data || []).map((item: any) => ({
    user_id: item.user_id,
    role: item.role,
    display_name: item.profiles?.display_name || '成员'
  }))
  tasks = (taskResult.data || []) as Task[]
  const ids = tasks.map((task) => task.id)
  if (ids.length) {
    const statusResult = await supabase.from('task_day_statuses').select('*').in('task_id', ids)
    statuses = (statusResult.data || []) as DayStatus[]
  } else {
    statuses = []
  }
  await scheduleReminders()
}

function subscribeRealtime() {
  if (!supabase || !space) return
  if (realtimeChannel) void supabase.removeChannel(realtimeChannel)
  realtimeChannel = supabase
    .channel(`space-${space.id}`)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'tasks', filter: `space_id=eq.${space.id}` }, refreshFromRealtime)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'task_day_statuses' }, refreshFromRealtime)
    .subscribe()
}

async function refreshFromRealtime() {
  await loadCalendarData()
  renderApp()
}

function tasksForDate(date: string) {
  return tasks.filter((task) => task.start_date <= date && task.end_date >= date)
}

function memberName(userId: string | null) {
  if (!userId) return '共同安排'
  return members.find((member) => member.user_id === userId)?.display_name || '成员'
}

function relevantStatus(task: Task, date: string) {
  const userId = task.assignee_id || session?.user.id
  return statuses.find((status) => status.task_id === task.id && status.task_date === date && status.user_id === userId)?.status || 'pending'
}

function completionForDate(date: string) {
  const ownTasks = tasksForDate(date).filter((task) => !task.assignee_id || task.assignee_id === session?.user.id)
  const complete = ownTasks.filter((task) => relevantStatus(task, date) === 'completed').length
  return { complete, total: ownTasks.length, rate: ownTasks.length ? Math.round(complete * 100 / ownTasks.length) : 0 }
}

function renderApp() {
  if (!space || !session) return
  const selectedTasks = tasksForDate(selectedDate)
  const progress = completionForDate(selectedDate)
  const currentMember = members.find((member) => member.user_id === session!.user.id)
  root.innerHTML = `
    <main class="shell">
      <header class="topbar">
        <div><div class="brand-kicker">${esc(space.name)}</div><h1>Focus Calendar</h1></div>
        <button class="icon-btn" id="app-settings" aria-label="设置">☰</button>
      </header>
      <section class="hero">
        <div class="hero-row">
          <div><div class="hero-date">${formatDay(selectedDate)}</div><div class="hero-copy">${progress.total ? `今天有 ${progress.total} 件属于你的事，慢慢完成。` : '给今天留一点呼吸，也留一点期待。'}</div></div>
          <div class="ring" style="--value:${progress.rate * 3.6}deg"><span>${progress.rate}%</span></div>
        </div>
      </section>
      <section class="card">
        <div class="calendar-head">
          <button id="prev-month">‹</button><div class="month-title">${calendarMonth.getFullYear()} 年 ${calendarMonth.getMonth() + 1} 月</div><button id="next-month">›</button>
        </div>
        <div class="weekdays"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div>
        <div class="calendar-grid">${calendarMarkup()}</div>
      </section>
      <div class="section-head"><div><h2>${formatDay(selectedDate)}的安排</h2><small>${selectedTasks.length} 项 · <span class="sync">云端已连接</span></small></div></div>
      <section class="task-list">
        ${selectedTasks.length ? selectedTasks.map(taskMarkup).join('') : '<div class="card empty">这一天还没有安排，点右下角开始规划。</div>'}
      </section>
      <button class="fab" id="add-task" aria-label="新建安排">＋</button>
    </main>`
  bindAppEvents()
  const title = document.querySelector('.brand-kicker')
  if (title && currentMember) title.setAttribute('title', `当前身份：${currentMember.display_name}`)
}

function calendarMarkup() {
  const year = calendarMonth.getFullYear()
  const month = calendarMonth.getMonth()
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  const gridStart = new Date(year, month, 1 - offset)
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart)
    date.setDate(gridStart.getDate() + index)
    const key = isoDate(date)
    const classes = ['day']
    if (date.getMonth() !== month) classes.push('outside')
    if (key === isoDate(new Date())) classes.push('today')
    if (key === selectedDate) classes.push('selected')
    if (tasksForDate(key).length) classes.push('has-task')
    return `<button class="${classes.join(' ')}" data-date="${key}">${date.getDate()}</button>`
  }).join('')
}

function taskMarkup(task: Task) {
  const status = relevantStatus(task, selectedDate)
  const isDone = status === 'completed'
  const canComplete = !task.assignee_id || task.assignee_id === session?.user.id
  const canEdit = task.creator_id === session?.user.id
  const time = task.all_day ? '全天' : `${(task.start_time || '').slice(0, 5)} - ${(task.end_time || '').slice(0, 5)}`
  const long = task.start_date !== task.end_date ? `${task.start_date.slice(5)} ~ ${task.end_date.slice(5)} · ` : ''
  const ownerClass = task.assignee_id && task.assignee_id !== session?.user.id ? 'partner' : ''
  return `<article class="task ${isDone ? 'done' : ''}" data-task="${task.id}">
    <div class="task-head">
      <div><div class="task-title">${esc(task.title)}</div><div class="task-meta">${long}${time}</div></div>
      <div class="task-actions">
        ${canEdit ? '<button class="icon-btn edit-task" aria-label="编辑">✎</button>' : ''}
        <button class="check ${isDone ? 'checked' : ''}" ${canComplete ? '' : 'disabled'} aria-label="切换完成状态">✓</button>
      </div>
    </div>
    <div class="chips"><span class="chip ${ownerClass}">${esc(memberName(task.assignee_id))}</span>${task.reminder_at ? '<span class="chip">有提醒</span>' : ''}</div>
  </article>`
}

function bindAppEvents() {
  document.querySelectorAll<HTMLButtonElement>('[data-date]').forEach((button) => button.addEventListener('click', () => {
    selectedDate = button.dataset.date!
    renderApp()
  }))
  document.querySelector('#prev-month')!.addEventListener('click', async () => {
    calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1)
    await loadCalendarData(); renderApp()
  })
  document.querySelector('#next-month')!.addEventListener('click', async () => {
    calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1)
    await loadCalendarData(); renderApp()
  })
  document.querySelector('#add-task')!.addEventListener('click', () => openTaskSheet())
  document.querySelector('#app-settings')!.addEventListener('click', openAppSettings)
  document.querySelectorAll<HTMLElement>('.task').forEach((card) => {
    const task = tasks.find((item) => item.id === card.dataset.task)!
    card.querySelector('.check')?.addEventListener('click', () => void toggleTask(task))
    card.querySelector('.edit-task')?.addEventListener('click', () => openTaskSheet(task))
  })
}

async function toggleTask(task: Task) {
  if (!supabase || !session || (task.assignee_id && task.assignee_id !== session.user.id)) return
  const current = relevantStatus(task, selectedDate)
  const { error } = await supabase.from('task_day_statuses').upsert({
    task_id: task.id,
    user_id: session.user.id,
    task_date: selectedDate,
    status: current === 'completed' ? 'pending' : 'completed'
  }, { onConflict: 'task_id,user_id,task_date' })
  if (!error) await refreshFromRealtime()
}

function openTaskSheet(task: Task | null = null) {
  editingTask = task
  const start = task?.start_date || selectedDate
  const end = task?.end_date || selectedDate
  const assignees = [`<option value="">共同安排</option>`, ...members.map((member) => `<option value="${member.user_id}" ${task?.assignee_id === member.user_id ? 'selected' : ''}>${esc(member.display_name)}</option>`)].join('')
  document.body.insertAdjacentHTML('beforeend', `
    <div class="sheet-backdrop" id="task-sheet"><section class="sheet">
      <h2>${task ? '编辑安排' : '新建安排'}</h2><div class="error" data-error hidden></div>
      <form id="task-form">
        <div class="field"><label>标题</label><input name="title" required maxlength="200" value="${esc(task?.title || '')}" placeholder="一起散步、复习英语、准备汇报" /></div>
        <div class="split">
          <div class="field"><label>开始日期</label><input name="start_date" type="date" required value="${start}" /></div>
          <div class="field"><label>结束日期</label><input name="end_date" type="date" required value="${end}" /></div>
        </div>
        <div class="split">
          <div class="field"><label>开始时间</label><input name="start_time" type="time" value="${(task?.start_time || '09:00').slice(0, 5)}" /></div>
          <div class="field"><label>结束时间</label><input name="end_time" type="time" value="${(task?.end_time || '10:00').slice(0, 5)}" /></div>
        </div>
        <div class="field"><label>安排归属</label><select name="assignee_id">${assignees}</select></div>
        <div class="field"><label>提醒时间（可选）</label><input name="reminder_at" type="datetime-local" value="${task?.reminder_at ? task.reminder_at.slice(0, 16) : ''}" /></div>
        <div class="field"><label>备注</label><textarea name="description" placeholder="地点、准备事项或想对 TA 说的话">${esc(task?.description || '')}</textarea></div>
        <div class="sheet-actions">${task ? '<button class="danger" id="delete-task" type="button">删除</button>' : ''}<button class="secondary" id="close-sheet" type="button">取消</button><button class="primary" type="submit">保存安排</button></div>
      </form>
    </section></div>`)
  document.querySelector('#close-sheet')!.addEventListener('click', closeSheet)
  document.querySelector('#task-sheet')!.addEventListener('click', (event) => { if (event.target === event.currentTarget) closeSheet() })
  document.querySelector<HTMLFormElement>('#task-form')!.addEventListener('submit', saveTask)
  document.querySelector('#delete-task')?.addEventListener('click', deleteTask)
}

function closeSheet() {
  document.querySelector('#task-sheet')?.remove()
  editingTask = null
}

async function saveTask(event: SubmitEvent) {
  event.preventDefault()
  if (!supabase || !space || !session) return
  const data = new FormData(event.currentTarget as HTMLFormElement)
  const startDate = String(data.get('start_date'))
  const endDate = String(data.get('end_date'))
  if (endDate < startDate) { setError('结束日期不能早于开始日期。'); return }
  const reminderValue = String(data.get('reminder_at') || '')
  const payload = {
    space_id: space.id,
    creator_id: session.user.id,
    assignee_id: String(data.get('assignee_id') || '') || null,
    title: String(data.get('title') || '').trim(),
    description: String(data.get('description') || '').trim(),
    start_date: startDate,
    end_date: endDate,
    start_time: String(data.get('start_time') || '') || null,
    end_time: String(data.get('end_time') || '') || null,
    all_day: false,
    reminder_at: reminderValue ? new Date(reminderValue).toISOString() : null
  }
  const response = editingTask
    ? await supabase.from('tasks').update(payload).eq('id', editingTask.id)
    : await supabase.from('tasks').insert(payload)
  if (response.error) { setError(response.error.message); return }
  closeSheet(); await refreshFromRealtime()
}

async function deleteTask() {
  if (!supabase || !editingTask || !confirm(`确认删除“${editingTask.title}”吗？`)) return
  const { error } = await supabase.from('tasks').delete().eq('id', editingTask.id)
  if (error) { setError(error.message); return }
  closeSheet(); await refreshFromRealtime()
}

function openAppSettings() {
  if (!space) return
  document.body.insertAdjacentHTML('beforeend', `
    <div class="sheet-backdrop" id="task-sheet"><section class="sheet">
      <h2>空间与账号</h2>
      <div class="invite"><small>邀请 TA 加入的代码</small><strong>${esc(space.invite_code)}</strong><small>最多两位成员，请只发给你的伴侣</small></div>
      <div class="field" style="margin-top:16px"><label>当前成员</label><div>${members.map((member) => `<span class="chip">${esc(member.display_name)} · ${member.role === 'owner' ? '创建者' : '成员'}</span>`).join(' ')}</div></div>
      <div class="sheet-actions"><button class="secondary" id="close-sheet">返回</button><button class="danger" id="logout">退出登录</button></div>
    </section></div>`)
  document.querySelector('#close-sheet')!.addEventListener('click', closeSheet)
  document.querySelector('#logout')!.addEventListener('click', async () => { await supabase?.auth.signOut(); closeSheet() })
}

async function scheduleReminders() {
  if (!Capacitor.isNativePlatform() || !session) return
  const permission = await LocalNotifications.checkPermissions()
  if (permission.display === 'prompt') await LocalNotifications.requestPermissions()
  const pending = tasks.filter((task) => {
    if (!task.reminder_at || (task.assignee_id && task.assignee_id !== session!.user.id)) return false
    return new Date(task.reminder_at).getTime() > Date.now()
  }).slice(0, 50)
  if (!pending.length) return
  await LocalNotifications.schedule({
    notifications: pending.map((task) => ({
      id: Math.abs(hashCode(task.id)) % 2147483647,
      title: '安排提醒',
      body: task.title,
      schedule: { at: new Date(task.reminder_at!) },
      extra: { taskId: task.id }
    }))
  })
}

function hashCode(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  return hash
}

void bootYanXu()
