# 安装与构建

## Windows 用户

从 GitHub Releases 下载 `YanXu-<版本>-windows.zip`，解压到独立目录后运行 `YanXu.exe`。不要只复制 EXE；`_internal` 目录是运行所需组件。

首次打开后在“设置 → 账户与跨端同步”填写：

- Supabase Project URL（可公开）
- Publishable/anon key（用于客户端，可公开但仍应限制权限）
- 邮箱与密码

绝不能在客户端填写或分发 `service_role`、Secret key。

## Android 用户

从 GitHub Releases 下载同版本 `YanXu-<版本>.apk`。首次侧载时 Android 8+ 会要求对当前来源开启“允许安装未知应用”。这是系统权限，研序不能也不会静默绕过。以后应用会在启动时自动检查更新，下载完成并校验后直接打开系统安装器，无需再手动寻找最新版。

> 当前旧安装包是 Debug 签名，不能被新的正式签名 APK 直接覆盖。首次迁移到 v2.2.0 正式版时，需要先确认数据已经同步到 Supabase，再卸载 Debug 版并安装正式版；登录原账号后云端数据会恢复。这个操作只需一次，从 v2.2.0 开始的后续 Release 都复用同一正式证书，可直接应用内更新。

## 开发构建

桌面端依赖 Python 3、PyQt5、PyInstaller；移动端依赖 Node.js、pnpm、JDK 21 和 Android SDK。统一发布命令：

```powershell
.\scripts\build_release.ps1 -Version 2.2.0 `
  -SupabaseUrl https://YOUR_PROJECT.supabase.co `
  -ReleaseNotes "本次更新说明"
```

脚本产出 Windows ZIP、正式签名 APK、SHA-256 和 `manifest.json`。

## Android 正式签名

正式 keystore 必须放在仓库之外，例如：

```text
%LOCALAPPDATA%\YanXu\signing\yanxu-release.jks
%LOCALAPPDATA%\YanXu\signing\keystore.properties
```

`keystore.properties` 包含 `storeFile`、`storePassword`、`keyAlias`、`keyPassword`。至少制作两份加密离线备份，并记录证书 SHA-256。今后所有 Release APK 必须保持相同 `applicationId`（`com.focuscalendar.couple`）并复用同一正式证书，否则 Android 无法覆盖安装。不要把 keystore 或密码提交到 GitHub、聊天、网盘公开链接或 Supabase Storage。
