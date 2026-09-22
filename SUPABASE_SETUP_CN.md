# 研序 YanXu V2 · Supabase 配置

## 当前状态

2026-08-12 已在当前项目执行 V2 数据迁移及 `yanxu-releases` 更新 bucket 迁移。新部署仍需按下列顺序执行脚本；旧登录令牌失效或忘记密码时，可在桌面端或 Android 端使用邮箱 Magic Link 登录原账号。

## 一、执行数据库脚本

1. 登录 Supabase Dashboard，打开研序使用的项目。
2. 打开 **SQL Editor**，点击 **New query**。
3. 如果这是一个全新的空项目：先复制并运行 `supabase/schema.sql` 的全部内容。
4. 再复制并运行 `supabase/migrations/20260811_yanxu_v2.sql` 的全部内容。
5. 最后运行 `supabase/migrations/20260812_yanxu_releases.sql`，创建跨端更新 bucket。
6. 看到 `Success. No rows returned` 即表示结构迁移执行成功。迁移脚本可以重复运行，不会删除旧任务。

如果原来的 Focus Calendar 双人同步已经正常使用，只需执行第 4 步的 V2 迁移，不要重新执行或重置数据库。

## 二、获取客户端连接信息

在项目的 **Connect** 对话框或 **Settings → API Keys** 中复制：

- Project URL：`https://你的项目编号.supabase.co`
- Publishable key：以 `sb_publishable_` 开头；旧项目也可继续使用 `anon` key

不要把 `secret`、`service_role` 或数据库密码填写到桌面端/手机端。客户端只能使用 Publishable/anon key，实际数据权限由登录账号与 RLS 控制。

## 三、连接电脑与手机

1. 打开桌面端 **设置 → 账户与跨端同步 → 账户与连接**。
2. 填写相同的 Project URL、Publishable key 和研序账号邮箱；可使用密码或邮箱登录链接登录。
3. 两台手机都填写同一 Project URL 和 Publishable key，但分别登录各自账号。
4. 第一位用户创建共享空间并生成邀请码；第二位用户用自己的账号加入该空间。

同步规则：

- 同一账号在电脑与手机之间同步自己的全部数据。
- 共享空间成员可以共同查看任务和项目。
- Review、Inbox、Focus 与周回顾按账号私有，不会暴露给另一位成员。
- 删除使用软删除标记同步，避免旧记录从另一台设备重新出现。

## 四、使用邮箱登录链接找回账号

研序使用 Supabase Auth 官方 Magic Link，并设置 `shouldCreateUser=false`，因此不会创建没有原共享空间的重复账号。

1. 在研序“账户与跨端同步”中填写原账号邮箱，点击“发送登录邮件”。
2. 在邮件客户端中右键或长按 **Sign in**，选择“复制链接地址”；不要先点击该链接。
3. 将链接粘贴回研序，点击“使用邮件链接登录”。
4. 研序只接受当前 Project URL 下的 `/auth/v1/verify` 链接，提取一次性 token hash 后交给同一个 Supabase 项目验证；原始链接不会保存。
5. 登录成功后，可以立即设置新密码。电脑与手机之后均可使用新密码登录。

2026-06-03 起，新建的 Supabase Free 项目使用默认 SMTP 时不能修改 Auth 邮件模板，因此无需尝试把默认 Magic Link 模板改成验证码模板。默认邮件服务只向项目组织成员邮箱发送，并有较严格的频率限制；面向其他用户正式发布前，应配置自己的 SMTP。

## 五、执行后的检查

回到桌面端点击“立即同步”，然后依次验证：

1. 新建任务并设置开始时间，手机端能看到。
2. 手机端修改任务，电脑端同步后能看到修改。
3. 删除任务后，另一端同步不会把它恢复。
4. 新建项目并关联任务，两端项目关系一致。
5. 两个不同账号之间可以看到共享任务/项目，但看不到彼此的 Inbox、复习和专注记录。
