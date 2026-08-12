# 研序 YanXu

研序是面向研究生与长期学习者的个人科研、学习和项目推进工作台。桌面端与 Android 端使用同一 Supabase 账号同步；手机端还支持两人共享空间。

[English README](README_EN.md) · [安装说明](docs/INSTALL_CN.md) · [同步与更新](docs/SYNC_AND_UPDATE_CN.md) · [参与贡献](CONTRIBUTING.md)

![研序今日页](docs/images/desktop-today.png)

## 功能

- 今日 Dashboard、任务、项目、复习、Inbox、日历、专注与周回顾
- 同一账号在 Windows 与 Android 之间同步
- 手机端两人共享任务与项目；个人复习、Inbox、专注记录保持私有
- 离线缓存与软删除同步，降低数据回弹风险
- 桌面端与 Android 共用 Supabase Storage `manifest.json` 检查更新
- 下载后执行 SHA-256 校验；校验失败不覆盖当前版本

## 技术结构

- Windows：Python、PyQt5、PyInstaller
- Android：TypeScript、Vite、Capacitor 7、原生 Java 更新插件
- 云端：Supabase Auth、Postgres、Storage

仓库只包含客户端可公开的代码和迁移脚本。Supabase `service_role`、Secret key、用户 token、Android 正式签名文件与密码均不得提交。

## 快速开始

1. 在 Supabase SQL Editor 依次执行 `supabase/schema.sql`、`supabase/migrations/20260811_yanxu_v2.sql` 和 `supabase/migrations/20260812_yanxu_releases.sql`。
2. 按[安装说明](docs/INSTALL_CN.md)构建或安装客户端。
3. 在客户端填写 Supabase Project URL 和 Publishable key；不要填写 `service_role`。
4. 发布新版本时使用 `scripts/build_release.ps1` 生成两个安装包和统一清单，再使用 `scripts/publish_release.ps1` 上传。

当前版本：`2.2.0`。

> Android 从旧 Debug 包迁移到 v2.2.0 正式版时需卸载旧包一次；请先同步数据。此后正式版本可持续应用内更新。
