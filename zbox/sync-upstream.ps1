# Sincroniza a branch zbox com o projeto original (elripalda/RecompLauncher)
# garantindo que o branding ZBOX e a trava de auto-update permaneçam intactos.
#
# Uso:
#   .\zbox\sync-upstream.ps1

$ErrorActionPreference = "Stop"

$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne "zbox") {
    Write-Host "Trocando para a branch zbox..."
    git checkout zbox
}

Write-Host "Buscando atualizacoes de upstream (elripalda/RecompLauncher)..."
git fetch upstream

Write-Host "Atualizando branch main espelho..."
git branch -f main upstream/main

Write-Host "Fazendo merge de upstream/main na branch zbox..."
git merge upstream/main --no-edit

Write-Host "Regenerando assets ZBOX..."
python zbox/generate-assets.py

Write-Host "Verificando integridade do branding e trava de auto-update..."
python zbox/verify-brand.py

Write-Host ""
Write-Host "Sincronizacao concluida com sucesso!"
Write-Host "Proximo passo: git push origin zbox (o GitHub Actions vai compilar e publicar a nova versao ZBOX)."
