# 参与贡献 / Contributing

欢迎提交 Issue 与 Pull Request。请保持研序“安静、理性、轻盈”的方向。电脑版修改运行 `python -m unittest discover -s tests -v`，检查长文本及 125%/150% 缩放；移动端有改动时再构建移动端。提交前执行 `scripts/security_scan.ps1`，截图只使用示例数据。

Issues and pull requests are welcome. Run desktop tests and verify long text and 125%/150% scaling. Build mobile when changing mobile code. Before committing, run `scripts/security_scan.ps1`; screenshots must use sample data only.

任何提交都不得包含真实账号、用户数据、访问令牌、Supabase Secret/service_role key、Android keystore 或签名密码。若怀疑密钥已泄露，请先在对应平台轮换密钥，再清理 Git 历史；仅删除最新提交并不足够。

Never commit real accounts, user data, access tokens, Supabase secret/service-role keys, Android keystores, or signing passwords. Rotate a suspected leaked credential before cleaning repository history.
