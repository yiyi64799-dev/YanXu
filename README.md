# 研序 YanXu

一个安静、轻量的个人科研与学习工作台。把任务、项目目标、知识卡片和专注记录放在一起，让下一步行动更清晰。

**当前开发版本：2.3.1 桌面预览版 · Windows · 本地优先 · 无需登录。**

[English](README_EN.md) · [安装与构建](docs/INSTALL_CN.md) · [电脑版使用说明](docs/DESKTOP_LOCAL_CN.md) · [更新日志](CHANGELOG.md) · [参与贡献](CONTRIBUTING.md)

![今日页：任务、项目下一步与轻量起步](docs/images/desktop-today-v231.png)

## 功能

- **今日与任务**：安排开始日期和目标完成日，完成与撤销；长文本在独立详情窗口阅读，不挤压首页。
- **项目推进**：展示目标、下一步、关联任务和完成情况。
- **知识卡片**：记录问题、答案与来源，关联项目；先回想再看答案，根据反馈安排下次自测。
- **成长记录**：汇总本周任务和专注时间、记录心得，一键复制进展用于组会。
- **轻量起步**：推荐一件预计 15 分钟内可执行的现有任务，不自动更改任务或启动计时。
- **日历、收集箱与专注**：按日期查看任务，捕获想法并转为任务，支持开始、暂停、继续和结束专注。
- **本地数据安全**：SQLite 事务保存、每日启动备份、导出与恢复；保留原缓存和历史记录。

## 界面预览

以下为软件实际渲染、使用示例数据的截图，不包含真实账户或用户记录。

### 任务详情

![独立任务详情窗口](docs/images/desktop-detail-v231.png)

### 项目目标

![项目目标、下一步和关联任务](docs/images/desktop-projects-v231.png)

### 知识卡片

![知识卡片与自测](docs/images/desktop-knowledge-v231.png)

### 成长记录

![本周节奏与完成足迹](docs/images/desktop-growth-v231.png)

## 快速运行

已在 Windows、Python 3.12 与 PyQt5 环境验证。克隆仓库后，在根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-desktop.txt
python yanxu_desktop.py
```

不需要 Supabase、账号或 Android 开发环境。测试与打包：

```powershell
python -m unittest discover -s tests -v
python -m PyInstaller --distpath release-desktop --workpath build-desktop YanXuDesktop.spec
```

运行 `release-desktop/YanXu/YanXu.exe`，必须保留同目录的 `_internal`。
[GitHub Releases](https://github.com/yiyi64799-dev/YanXu/releases) 可能仍包含旧版跨端安装包；源码版本与已发布安装包不一定同步，请核对版本说明。

## 版本边界

| 内容 | 当前状态 |
| --- | --- |
| 新版 Windows 入口 | `yanxu_desktop.py`，本地保存，无需登录 |
| 旧版跨端入口 | `yanxu_v2_app.py`，保留兼容代码 |
| Android 与 Supabase | 保留于 `mobile/` 和 `supabase/`，本轮未升级 |
| 手机同步 | **新版暂不启用**，本地新增修改不会同步到手机 |
| 自动安装更新 | **新版暂不启用**，防止旧跨端发布覆盖本地版 |

数据位于 `%LOCALAPPDATA%\YanXu`。首次启动备份并导入本机旧缓存，不删除账号配置，也不重复导入覆盖新数据。仅存在云端、尚未缓存的记录不会自动下载。

提醒需要程序保持运行，可启用关闭到托盘。异常退出时正在进行的专注片段尚不能恢复；重复规则保留，但暂不自动生成重复任务。详见[使用说明](docs/DESKTOP_LOCAL_CN.md)。

## 代码结构

```text
yanxu_desktop.py       桌面页面与交互
yanxu_widgets.py       导航与长文本组件
yanxu_store.py         本地数据库、迁移与备份
yanxu_insights.py      周统计、自测调度与轻量起步
tests/                离线保存、恢复、界面与统计测试
mobile/               旧版 Android 客户端
supabase/             旧版数据库结构与迁移
```

不提交账号、用户数据、访问令牌、Supabase Secret/service_role key、签名文件或构建缓存。旧版云端流程见[同步与更新](docs/SYNC_AND_UPDATE_CN.md)。
