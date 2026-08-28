create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  processor_project_id text,
  title text not null,
  source_name text,
  source_url text,
  stage text not null default 'pending' check (stage in ('pending','import','analyze','curate','refine','render','complete','failed')),
  progress smallint not null default 0 check (progress between 0 and 100),
  message text not null default 'Aguardando processamento',
  error text,
  media jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.clips (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  title text not null,
  start_ms integer not null check (start_ms >= 0),
  end_ms integer not null check (end_ms > start_ms),
  quality_score smallint not null check (quality_score between 0 and 100),
  output_key text,
  output_url text,
  score_breakdown jsonb,
  reasons jsonb,
  transcript_excerpt text,
  created_at timestamptz not null default now()
);

create index if not exists projects_owner_created_idx on public.projects(owner_id, created_at desc);
create index if not exists clips_project_score_idx on public.clips(project_id, quality_score desc);

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.clips enable row level security;

create policy "profiles are self-readable" on public.profiles for select using (auth.uid() = id);
create policy "profiles are self-editable" on public.profiles for update using (auth.uid() = id);
create policy "projects owner access" on public.projects for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "clips follow project owner" on public.clips for all using (
  exists (select 1 from public.projects p where p.id = clips.project_id and p.owner_id = auth.uid())
) with check (
  exists (select 1 from public.projects p where p.id = clips.project_id and p.owner_id = auth.uid())
);

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name) values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email));
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
for each row execute procedure public.handle_new_user();
