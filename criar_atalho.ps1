# Cria o atalho "Kairos" na área de trabalho, com o ícone do app.
# Uso (na pasta do projeto, no PowerShell):
#     powershell -ExecutionPolicy Bypass -File .\criar_atalho.ps1
#
# O atalho roda o iniciar.pyw com o pythonw.exe do venv (o "w" = sem janela de terminal).

$ErrorActionPreference = "Stop"
$projeto = $PSScriptRoot
$pythonw = Join-Path $projeto "venv\Scripts\pythonw.exe"
$iniciar = Join-Path $projeto "iniciar.pyw"
$icone   = Join-Path $projeto "static\img\kairos.ico"

foreach ($arquivo in @($pythonw, $iniciar, $icone)) {
    if (-not (Test-Path $arquivo)) {
        Write-Error "Não encontrei $arquivo. Rode este script na pasta do projeto, depois de criar o venv."
    }
}

$area = [Environment]::GetFolderPath("Desktop")
$destino = Join-Path $area "Kairos.lnk"

$shell = New-Object -ComObject WScript.Shell
$atalho = $shell.CreateShortcut($destino)
$atalho.TargetPath = $pythonw
$atalho.Arguments = "`"$iniciar`""
$atalho.WorkingDirectory = $projeto
$atalho.IconLocation = "$icone,0"
$atalho.Description = "Kairos - tarefas, reuniões e faculdade num lugar só"
$atalho.Save()

Write-Host "Atalho criado: $destino"
