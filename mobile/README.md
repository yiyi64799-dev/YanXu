# 研序 YanXu Mobile

This is the Android/mobile client for YanXu V2. The same account synchronizes between
desktop and mobile; a two-member space shares tasks and projects, while Review, Inbox,
Focus sessions, and weekly reviews remain private to each account.

## Supabase setup

1. Create a Supabase project.
2. Open **SQL Editor** and run `../supabase/schema.sql` once, then run
   `../supabase/migrations/20260811_yanxu_v2.sql`.
3. In **Project Settings > API**, copy the Project URL and the publishable key (or legacy anon key).
4. Do not put a `service_role` or secret key into this app.

On first launch, the app asks for the Project URL and publishable key. Each partner then creates a separate email/password account. The first person creates a couple space and shares its eight-character invite code; the second person joins with that code.

## Data boundaries

- Both members can read and update shared tasks and projects; soft deletion is synced.
- Review, Inbox, Focus sessions, and weekly reviews are private to the account that owns them.
- A task can belong to one member or be shared. The V2 task status is synchronized directly.
- Row Level Security is enabled on every exposed table.

## Local build

```powershell
npm install
npm run build
npx cap add android
npm run android:apk
```

The debug APK is generated under `android/app/build/outputs/apk/debug/` after Android SDK and a current JDK are configured. Production builds use `npm run android:release` and require the external signing configuration described in `../docs/INSTALL_EN.md`. The app checks the shared Supabase release manifest at startup and only downloads a newer version.
