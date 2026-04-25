$ErrorActionPreference = "Stop"

git config core.hooksPath .kiro/hooks
Write-Host "已启用仓库 hooks 路径: .kiro/hooks"
