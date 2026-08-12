-- Focus Calendar couple-space schema.
-- Run this file once in the Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '新成员',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.spaces (
  id uuid primary key default gen_random_uuid(),
  name text not null default '我们的日历',
  invite_code text not null unique default upper(substr(encode(gen_random_bytes(8), 'hex'), 1, 8)),
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table if not exists public.space_members (
  space_id uuid not null references public.spaces(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'member')),
  joined_at timestamptz not null default now(),
  primary key (space_id, user_id)
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  space_id uuid not null references public.spaces(id) on delete cascade,
  creator_id uuid not null references auth.users(id) on delete cascade,
  assignee_id uuid references auth.users(id) on delete set null,
  title text not null check (char_length(trim(title)) between 1 and 200),
  description text not null default '',
  start_date date not null,
  end_date date not null,
  start_time time,
  end_time time,
  all_day boolean not null default false,
  reminder_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date >= start_date)
);

create table if not exists public.task_day_statuses (
  task_id uuid not null references public.tasks(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  task_date date not null,
  status text not null default 'pending' check (status in ('pending', 'urgent', 'deferred', 'completed')),
  updated_at timestamptz not null default now(),
  primary key (task_id, user_id, task_date)
);

create index if not exists tasks_space_dates_idx on public.tasks(space_id, start_date, end_date);
create index if not exists tasks_assignee_idx on public.tasks(assignee_id);
create index if not exists space_members_user_idx on public.space_members(user_id, space_id);
create index if not exists task_day_statuses_user_date_idx on public.task_day_statuses(user_id, task_date);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at before update on public.profiles
for each row execute function public.touch_updated_at();

drop trigger if exists tasks_touch_updated_at on public.tasks;
create trigger tasks_touch_updated_at before update on public.tasks
for each row execute function public.touch_updated_at();

drop trigger if exists statuses_touch_updated_at on public.task_day_statuses;
create trigger statuses_touch_updated_at before update on public.task_day_statuses
for each row execute function public.touch_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles(id, display_name)
  values (new.id, coalesce(nullif(new.raw_user_meta_data ->> 'display_name', ''), split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
for each row execute function public.handle_new_user();

create or replace function public.is_space_member(target_space uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.space_members
    where space_id = target_space and user_id = (select auth.uid())
  );
$$;

create or replace function public.create_couple_space(space_name text, member_name text)
returns table(space_id uuid, invite_code text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  created_space public.spaces;
begin
  if (select auth.uid()) is null then
    raise exception 'Authentication required';
  end if;
  insert into public.profiles(id, display_name)
  values ((select auth.uid()), coalesce(nullif(trim(member_name), ''), '我'))
  on conflict (id) do update set display_name = excluded.display_name;
  insert into public.spaces(name, created_by)
  values (coalesce(nullif(trim(space_name), ''), '我们的日历'), (select auth.uid()))
  returning * into created_space;
  insert into public.space_members(space_id, user_id, role)
  values (created_space.id, (select auth.uid()), 'owner');
  return query select created_space.id, created_space.invite_code;
end;
$$;

create or replace function public.join_couple_space(code text, member_name text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_space uuid;
  member_count integer;
begin
  if (select auth.uid()) is null then
    raise exception 'Authentication required';
  end if;
  select id into target_space from public.spaces
  where invite_code = upper(trim(code)) for update;
  if target_space is null then
    raise exception 'Invite code not found';
  end if;
  select count(*) into member_count from public.space_members where space_id = target_space;
  if member_count >= 2 and not exists (
    select 1 from public.space_members where space_id = target_space and user_id = (select auth.uid())
  ) then
    raise exception 'This couple space already has two members';
  end if;
  insert into public.profiles(id, display_name)
  values ((select auth.uid()), coalesce(nullif(trim(member_name), ''), 'TA'))
  on conflict (id) do update set display_name = excluded.display_name;
  insert into public.space_members(space_id, user_id, role)
  values (target_space, (select auth.uid()), 'member')
  on conflict do nothing;
  return target_space;
end;
$$;

revoke all on function public.is_space_member(uuid) from public;
revoke all on function public.create_couple_space(text, text) from public;
revoke all on function public.join_couple_space(text, text) from public;
grant execute on function public.is_space_member(uuid) to authenticated;
grant execute on function public.create_couple_space(text, text) to authenticated;
grant execute on function public.join_couple_space(text, text) to authenticated;

alter table public.profiles enable row level security;
alter table public.spaces enable row level security;
alter table public.space_members enable row level security;
alter table public.tasks enable row level security;
alter table public.task_day_statuses enable row level security;

drop policy if exists "profiles shared with couple" on public.profiles;
create policy "profiles shared with couple" on public.profiles for select to authenticated
using (
  id = (select auth.uid()) or exists (
    select 1 from public.space_members mine
    join public.space_members theirs on theirs.space_id = mine.space_id
    where mine.user_id = (select auth.uid()) and theirs.user_id = profiles.id
  )
);

drop policy if exists "profiles update self" on public.profiles;
create policy "profiles update self" on public.profiles for update to authenticated
using (id = (select auth.uid())) with check (id = (select auth.uid()));

drop policy if exists "members view spaces" on public.spaces;
create policy "members view spaces" on public.spaces for select to authenticated
using ((select public.is_space_member(id)));

drop policy if exists "members view membership" on public.space_members;
create policy "members view membership" on public.space_members for select to authenticated
using ((select public.is_space_member(space_id)));

drop policy if exists "members view tasks" on public.tasks;
create policy "members view tasks" on public.tasks for select to authenticated
using ((select public.is_space_member(space_id)));

drop policy if exists "members create tasks" on public.tasks;
create policy "members create tasks" on public.tasks for insert to authenticated
with check (
  creator_id = (select auth.uid())
  and (select public.is_space_member(space_id))
  and (
    assignee_id is null or exists (
      select 1 from public.space_members
      where space_members.space_id = tasks.space_id and space_members.user_id = tasks.assignee_id
    )
  )
);

drop policy if exists "creators edit tasks" on public.tasks;
create policy "creators edit tasks" on public.tasks for update to authenticated
using (creator_id = (select auth.uid()))
with check (creator_id = (select auth.uid()) and (select public.is_space_member(space_id)));

drop policy if exists "creators delete tasks" on public.tasks;
create policy "creators delete tasks" on public.tasks for delete to authenticated
using (creator_id = (select auth.uid()));

drop policy if exists "members view daily statuses" on public.task_day_statuses;
create policy "members view daily statuses" on public.task_day_statuses for select to authenticated
using (
  exists (
    select 1 from public.tasks
    where tasks.id = task_day_statuses.task_id and (select public.is_space_member(tasks.space_id))
  )
);

drop policy if exists "users create own daily status" on public.task_day_statuses;
create policy "users create own daily status" on public.task_day_statuses for insert to authenticated
with check (
  user_id = (select auth.uid()) and exists (
    select 1 from public.tasks
    where tasks.id = task_day_statuses.task_id
      and task_day_statuses.task_date between tasks.start_date and tasks.end_date
      and (tasks.assignee_id is null or tasks.assignee_id = (select auth.uid()))
      and (select public.is_space_member(tasks.space_id))
  )
);

drop policy if exists "users update own daily status" on public.task_day_statuses;
create policy "users update own daily status" on public.task_day_statuses for update to authenticated
using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "users delete own daily status" on public.task_day_statuses;
create policy "users delete own daily status" on public.task_day_statuses for delete to authenticated
using (user_id = (select auth.uid()));

do $$
begin
  if not exists (
    select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'tasks'
  ) then
    alter publication supabase_realtime add table public.tasks;
  end if;
  if not exists (
    select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'task_day_statuses'
  ) then
    alter publication supabase_realtime add table public.task_day_statuses;
  end if;
end $$;
