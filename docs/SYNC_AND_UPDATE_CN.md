# 跨端同步与应用内更新

## 同步模型

Windows 和 Android 使用同一 Supabase 项目与同一账号。共享空间内的任务和项目可由两位成员共同查看；复习、Inbox 和专注记录按用户隔离。云端是同步事实来源，本地缓存用于离线读取和暂存。删除使用软删除标记，避免另一端把旧数据重新拉回。

## 客户端检查更新

两个客户端默认读取：

```text
https://<project>.supabase.co/storage/v1/object/public/yanxu-releases/manifest.json
```

桌面端在“设置 → 系统更新”提供自动检查、手动检查和稳定版/预览版。Android 在启动后静默检查一次，并在发现新版时显示“立即更新 / 稍后”。自动检查不会重复下载当前版本。

下载完成后两端都会核对清单中的 SHA-256。桌面端只在校验和解压均成功后退出并替换应用目录，同时保留一个 `YanXu.rollback-*` 备份目录。Android 将 APK 放入应用缓存，校验后通过 FileProvider 打开系统安装器；不能静默安装。

## 发布新版

1. 更新桌面 `APP_VERSION`、移动端 `APP_VERSION`、`package.json`、Android `versionName` 和递增的 `versionCode`。
2. 运行 `scripts/build_release.ps1`。脚本构建 Windows ZIP 和正式签名 APK，并生成真实 SHA-256 的 `manifest.json`。
3. 人工检查安装包、更新说明、版本号与哈希。
4. 只在当前管理员终端临时设置 `SUPABASE_SERVICE_ROLE_KEY`，运行：

```powershell
$env:SUPABASE_SERVICE_ROLE_KEY = '<仅当前终端使用的服务端密钥>'
.\scripts\publish_release.ps1 `
  -SupabaseUrl https://YOUR_PROJECT.supabase.co `
  -ReleaseDirectory .\artifacts\v2.2.0
Remove-Item Env:\SUPABASE_SERVICE_ROLE_KEY
```

脚本先上传 ZIP 和 APK，最后上传 `manifest.json`，避免客户端看到尚未上传完整的版本。服务端密钥不会写入任何输出文件。

## 回滚

- Windows 紧急回滚：关闭研序，把损坏目录移走，将最近的 `YanXu.rollback-*` 改回原安装目录名。
- 线上回滚：不要把 `manifest.json` 指向缺失文件。推荐用旧代码重新构建一个更高版本号的新修复版，上传包后最后更新清单。
- Android 不应直接发布更低 `versionCode` 的 APK，因为系统通常拒绝降级。应使用旧代码、相同 applicationId、同一签名证书和更高 `versionCode` 构建回滚版。

