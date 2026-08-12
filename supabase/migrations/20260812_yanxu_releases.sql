-- YanXu cross-platform public release channel.
-- Public clients may read objects. Uploads remain restricted to Dashboard/service_role.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'yanxu-releases',
  'yanxu-releases',
  true,
  314572800,
  array['application/json', 'application/zip', 'application/x-zip-compressed', 'application/vnd.android.package-archive']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Intentionally no INSERT/UPDATE/DELETE policy for anon or authenticated users.
-- Public bucket reads are served through /storage/v1/object/public/yanxu-releases/*.

