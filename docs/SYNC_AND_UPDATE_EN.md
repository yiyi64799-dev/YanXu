# Cross-device sync and in-app updates

Windows and Android use the same Supabase project and account. Tasks and projects are shared inside a two-member space; reviews, Inbox items, and focus sessions remain user-private. The cloud is the source of truth, with local caching for offline use. Soft-delete markers prevent deleted records from returning on another device.

Both clients read the public `yanxu-releases/manifest.json`. Desktop exposes automatic/manual checks and stable/preview channels. Android checks once at startup and offers **Update now** or **Later**. It does not download the already installed version again.

Both clients verify SHA-256 before installation. Desktop stages and validates the entire ZIP before replacing the application after exit, retaining a rollback directory. Android downloads to app cache and uses FileProvider to open the system installer. Silent installation is intentionally unsupported.

For each release, increment every version field and Android `versionCode`, build with `scripts/build_release.ps1`, verify the files, and publish with `scripts/publish_release.ps1`. Packages are uploaded before the manifest. Keep `SUPABASE_SERVICE_ROLE_KEY` only in the current administrative shell and remove it immediately afterward.

For Android rollback, rebuild the previous known-good source with a higher `versionCode`, the same application ID, and the same signing certificate. A lower version code is normally rejected by Android.

