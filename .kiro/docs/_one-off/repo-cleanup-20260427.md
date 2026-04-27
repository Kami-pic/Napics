# 仓库清理记录 - 2026-04-27

## 背景
仓库根目录下存在若干与项目核心逻辑无关的临时 PowerShell 脚本，这些脚本是此前用于强行卸载“微步终端安全管理平台”（ThreatBook Agent）而创建的。

## 处理动作
经用户确认，删除了以下 4 个冗余脚本：
1. `simple_del.ps1`
2. `force_del.ps1`
3. `del_on_reboot.ps1`
4. `clean_registry.ps1`

## 验证
- [x] 文件已从磁盘移除。
- [x] 项目核心逻辑（backend/frontend）未受影响。
