-- YanXu V2 migration. Run this AFTER supabase/schema.sql. It is safe to re-run.
-- The migration only adds data and keeps legacy calendar records intact.

create extension if not exists pgcrypto;

-- Existing calendar entries become V2 tasks without a data copy.
alter table public.tasks add column if not exists status text not null default 'pending';
alter table public.tasks add column if not exists priority text not null default 'normal';
alter table public.tasks add column if not exists project_id uuid;
alter table public.tasks add column if not exists due_at timestamptz;
alter table public.tasks add column if not exists estimated_minutes integer;
alter table public.tasks add column if not exists actual_minutes integer not null default 0;
alter table public.tasks add column if not exists reminder_policy jsonb not null default '{}'::jsonb;
alter table public.tasks add column if not exists repeat_rule jsonb not null default '{}'::jsonb;
alter table public.tasks add column if not exists review_enabled boolean not null default false;
alter table public.tasks add column if not exists follow_up_at timestamptz;
alter table public.tasks add column if not exists blocker_reason text not null default '';
alter table public.tasks add column if not exists visibility text not null default 'shared';
alter table public.tasks add column if not exists deleted_at timestamptz;
alter table public.tasks add column if not exists version integer not null default 1;
alter table public.tasks drop constraint if exists tasks_status_check;
alter table public.tasks add constraint tasks_status_check check (status in ('pending', 'in_progress', 'waiting', 'blocked', 'completed', 'cancelled'));
alter table public.tasks drop constraint if exists tasks_priority_check;
alter table public.tasks add constraint tasks_priority_check check (priority in ('low', 'normal', 'high', 'today'));
alter table public.tasks drop constraint if exists tasks_visibility_check;
alter table public.tasks add constraint tasks_visibility_check check (visibility in ('shared', 'private'));
alter table public.tasks drop constraint if exists tasks_estimated_minutes_check;
alter table public.tasks add constraint tasks_estimated_minutes_check check (estimated_minutes is null or estimated_minutes > 0);

create table if not exists public.areas (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, name text not null check (char_length(trim(name)) between 1 and 80),
 color text not null default '#176b61', visibility text not null default 'shared' check (visibility in ('shared','private')),
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());

create table if not exists public.projects (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, area_id uuid references public.areas(id) on delete set null,
 name text not null check (char_length(trim(name)) between 1 and 160), goal text not null default '',
 status text not null default 'active' check (status in ('active','paused','completed','cancelled')),
 progress integer not null default 0 check (progress between 0 and 100), next_action text not null default '',
 start_at date, due_at date, notes text not null default '', visibility text not null default 'shared' check (visibility in ('shared','private')),
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check (due_at is null or start_at is null or due_at >= start_at));
alter table public.tasks drop constraint if exists tasks_project_id_fkey;
alter table public.tasks add constraint tasks_project_id_fkey foreign key (project_id) references public.projects(id) on delete set null;

create table if not exists public.milestones (
 id uuid primary key default gen_random_uuid(), project_id uuid not null references public.projects(id) on delete cascade,
 title text not null check (char_length(trim(title)) between 1 and 160), due_at date, weight integer not null default 1 check (weight > 0),
 status text not null default 'pending' check (status in ('pending','completed','cancelled')), completed_at timestamptz, deleted_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now());

create table if not exists public.reviews (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, source_task_id uuid references public.tasks(id) on delete set null,
 title text not null check (char_length(trim(title)) between 1 and 200), note text not null default '',
 schedule_mode text not null default 'standard' check (schedule_mode in ('light','standard','custom','adaptive')),
 intervals integer[] not null default array[1,2,4,7,15,30], current_step integer not null default 0 check (current_step >= 0),
 next_review_at timestamptz not null default now(), last_rating text check (last_rating in ('forgot','vague','remembered','mastered')),
 is_active boolean not null default true, deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.review_logs (
 id uuid primary key default gen_random_uuid(), review_id uuid not null references public.reviews(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, rating text not null check (rating in ('forgot','vague','remembered','mastered')),
 reviewed_at timestamptz not null default now(), note text not null default '');
create table if not exists public.focus_sessions (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, task_id uuid references public.tasks(id) on delete set null,
 started_at timestamptz not null, ended_at timestamptz, duration_minutes integer not null default 0 check (duration_minutes >= 0), note text not null default '',
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.inbox_items (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, content text not null check (char_length(trim(content)) between 1 and 500),
 status text not null default 'inbox' check (status in ('inbox','converted','dismissed')), converted_type text check (converted_type in ('task','project','review')),
 converted_id uuid, deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.weekly_reviews (
 id uuid primary key default gen_random_uuid(), space_id uuid not null references public.spaces(id) on delete cascade,
 owner_id uuid not null references auth.users(id) on delete cascade, period_start date not null, highlights text not null default '',
 next_priorities jsonb not null default '[]'::jsonb, deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(owner_id, period_start));

create index if not exists tasks_v2_active_idx on public.tasks(space_id, deleted_at, start_date, due_at);
create index if not exists projects_space_active_idx on public.projects(space_id, deleted_at, status);
create index if not exists reviews_owner_due_idx on public.reviews(owner_id, is_active, deleted_at, next_review_at);
create index if not exists inbox_owner_active_idx on public.inbox_items(owner_id, deleted_at, status);
create index if not exists focus_owner_started_idx on public.focus_sessions(owner_id, deleted_at, started_at);

-- RLS: Tasks/projects are shareable; reviews, focus, inbox and weekly review are personal.
alter table public.areas enable row level security; alter table public.projects enable row level security; alter table public.milestones enable row level security;
alter table public.reviews enable row level security; alter table public.review_logs enable row level security; alter table public.focus_sessions enable row level security;
alter table public.inbox_items enable row level security; alter table public.weekly_reviews enable row level security;
create or replace function public.can_read_v2_item(target_space uuid, target_owner uuid, target_visibility text)
returns boolean language sql stable security definer set search_path = '' as $$
 select target_owner = (select auth.uid()) or (target_visibility = 'shared' and public.is_space_member(target_space)); $$;
create or replace function public.can_write_v2_item(target_space uuid, target_owner uuid)
returns boolean language sql stable security definer set search_path = '' as $$
 select target_owner = (select auth.uid()) and public.is_space_member(target_space); $$;
revoke all on function public.can_read_v2_item(uuid, uuid, text) from public; revoke all on function public.can_write_v2_item(uuid, uuid) from public;
grant execute on function public.can_read_v2_item(uuid, uuid, text) to authenticated; grant execute on function public.can_write_v2_item(uuid, uuid) to authenticated;

drop policy if exists v2_areas_read on public.areas; drop policy if exists v2_areas_write on public.areas;
create policy v2_areas_read on public.areas for select to authenticated using (public.can_read_v2_item(space_id, owner_id, visibility));
create policy v2_areas_write on public.areas for all to authenticated using (public.can_write_v2_item(space_id, owner_id)) with check (public.can_write_v2_item(space_id, owner_id));
drop policy if exists v2_projects_read on public.projects; drop policy if exists v2_projects_write on public.projects;
create policy v2_projects_read on public.projects for select to authenticated using (public.can_read_v2_item(space_id, owner_id, visibility));
create policy v2_projects_write on public.projects for all to authenticated using (public.can_write_v2_item(space_id, owner_id)) with check (public.can_write_v2_item(space_id, owner_id));
drop policy if exists v2_milestones_read on public.milestones; drop policy if exists v2_milestones_write on public.milestones;
create policy v2_milestones_read on public.milestones for select to authenticated using (exists (select 1 from public.projects p where p.id = milestones.project_id and public.can_read_v2_item(p.space_id,p.owner_id,p.visibility)));
create policy v2_milestones_write on public.milestones for all to authenticated using (exists (select 1 from public.projects p where p.id = milestones.project_id and public.can_write_v2_item(p.space_id,p.owner_id))) with check (exists (select 1 from public.projects p where p.id = milestones.project_id and public.can_write_v2_item(p.space_id,p.owner_id)));

drop policy if exists v2_reviews_private on public.reviews; drop policy if exists v2_reviews_write on public.reviews;
create policy v2_reviews_private on public.reviews for select to authenticated using (owner_id = (select auth.uid()));
create policy v2_reviews_write on public.reviews for all to authenticated using (public.can_write_v2_item(space_id,owner_id)) with check (public.can_write_v2_item(space_id,owner_id));
drop policy if exists v2_review_logs_private on public.review_logs; drop policy if exists v2_review_logs_write on public.review_logs;
create policy v2_review_logs_private on public.review_logs for select to authenticated using (owner_id = (select auth.uid()));
create policy v2_review_logs_write on public.review_logs for all to authenticated using (owner_id = (select auth.uid()) and exists (select 1 from public.reviews r where r.id=review_logs.review_id and r.owner_id=(select auth.uid()))) with check (owner_id=(select auth.uid()) and exists (select 1 from public.reviews r where r.id=review_logs.review_id and r.owner_id=(select auth.uid())));
drop policy if exists v2_focus_private on public.focus_sessions; drop policy if exists v2_focus_write on public.focus_sessions;
create policy v2_focus_private on public.focus_sessions for select to authenticated using (owner_id=(select auth.uid()));
create policy v2_focus_write on public.focus_sessions for all to authenticated using (public.can_write_v2_item(space_id,owner_id)) with check (public.can_write_v2_item(space_id,owner_id));
drop policy if exists v2_inbox_private on public.inbox_items; drop policy if exists v2_inbox_write on public.inbox_items;
create policy v2_inbox_private on public.inbox_items for select to authenticated using (owner_id=(select auth.uid()));
create policy v2_inbox_write on public.inbox_items for all to authenticated using (public.can_write_v2_item(space_id,owner_id)) with check (public.can_write_v2_item(space_id,owner_id));
drop policy if exists v2_weekly_private on public.weekly_reviews; drop policy if exists v2_weekly_write on public.weekly_reviews;
create policy v2_weekly_private on public.weekly_reviews for select to authenticated using (owner_id=(select auth.uid()));
create policy v2_weekly_write on public.weekly_reviews for all to authenticated using (public.can_write_v2_item(space_id,owner_id)) with check (public.can_write_v2_item(space_id,owner_id));

-- Existing task RLS becomes workspace-editable. Deletion is a synchronized soft delete in the client.
drop policy if exists "creators edit tasks" on public.tasks; drop policy if exists "creators delete tasks" on public.tasks; drop policy if exists "members edit v2 tasks" on public.tasks;
create policy "members edit v2 tasks" on public.tasks for update to authenticated using ((select public.is_space_member(space_id))) with check ((select public.is_space_member(space_id)));
create or replace function public.touch_v2_updated_at() returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at = now(); if tg_table_name = 'tasks' then new.version = old.version + 1; end if; return new; end; $$;
drop trigger if exists tasks_touch_v2_updated_at on public.tasks; create trigger tasks_touch_v2_updated_at before update on public.tasks for each row execute function public.touch_v2_updated_at();
drop trigger if exists projects_touch_v2_updated_at on public.projects; create trigger projects_touch_v2_updated_at before update on public.projects for each row execute function public.touch_v2_updated_at();
drop trigger if exists milestones_touch_v2_updated_at on public.milestones; create trigger milestones_touch_v2_updated_at before update on public.milestones for each row execute function public.touch_v2_updated_at();
drop trigger if exists reviews_touch_v2_updated_at on public.reviews; create trigger reviews_touch_v2_updated_at before update on public.reviews for each row execute function public.touch_v2_updated_at();
drop trigger if exists focus_touch_v2_updated_at on public.focus_sessions; create trigger focus_touch_v2_updated_at before update on public.focus_sessions for each row execute function public.touch_v2_updated_at();
drop trigger if exists inbox_touch_v2_updated_at on public.inbox_items; create trigger inbox_touch_v2_updated_at before update on public.inbox_items for each row execute function public.touch_v2_updated_at();
drop trigger if exists weekly_touch_v2_updated_at on public.weekly_reviews; create trigger weekly_touch_v2_updated_at before update on public.weekly_reviews for each row execute function public.touch_v2_updated_at();
do $$ declare t text; begin foreach t in array array['areas','projects','milestones','reviews','review_logs','focus_sessions','inbox_items','weekly_reviews'] loop
 if not exists (select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename=t) then execute format('alter publication supabase_realtime add table public.%I',t); end if; end loop; end $$;

-- Used by desktop/mobile Focus completion. The owner/member check prevents arbitrary increments.
create or replace function public.increment_task_actual_minutes(task_uuid uuid, minutes_to_add integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if minutes_to_add < 0 or not exists (select 1 from public.tasks where id = task_uuid and public.is_space_member(space_id)) then
    raise exception 'Task is not available in your space';
  end if;
  update public.tasks set actual_minutes = actual_minutes + minutes_to_add where id = task_uuid;
end;
$$;
revoke all on function public.increment_task_actual_minutes(uuid, integer) from public;
grant execute on function public.increment_task_actual_minutes(uuid, integer) to authenticated;
