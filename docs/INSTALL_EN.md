# Installation and build

## Windows

Download `YanXu-<version>-windows.zip` from GitHub Releases, extract it into its own directory, and run `YanXu.exe`. Keep the `_internal` directory next to the executable.

In Settings, enter your Supabase Project URL, Publishable/anon key, email, and password. Never place a `service_role` or secret key in a client.

## Android

Download the matching `YanXu-<version>.apk`. Android 8+ asks you to allow installs from the current source on the first sideload. YanXu cannot silently install an APK. After installation, the app checks for updates at startup, verifies the downloaded APK, and opens Android's system installer.

The previous APK used a debug certificate and cannot be overwritten by the new production-signed build. For the one-time migration to v2.2.0, confirm that your data is synchronized, uninstall the debug app, and install the production APK. Sign in again to restore cloud data. Every release after v2.2.0 reuses the same production certificate and supports normal in-app upgrades.

## Release build

The desktop build needs Python, PyQt5, and PyInstaller. Android needs Node.js, pnpm, JDK 21, and the Android SDK.

```powershell
.\scripts\build_release.ps1 -Version 2.2.0 `
  -SupabaseUrl https://YOUR_PROJECT.supabase.co `
  -ReleaseNotes "Release notes"
```

The production keystore and `keystore.properties` belong under `%LOCALAPPDATA%\YanXu\signing`, outside this repository. Keep encrypted offline backups. Every release must retain application ID `com.focuscalendar.couple` and use the same certificate, or Android cannot update the installed app.
