param([string]$OutputPath)
$ErrorActionPreference='Stop'
$workspace=Split-Path $PSScriptRoot -Parent
if(!$OutputPath){$OutputPath=Join-Path $workspace 'artifacts\PersonaLiveView-0.5.8'}
$package=[IO.Path]::GetFullPath($OutputPath)
& dotnet build (Join-Path $workspace 'module\Voxta.Modules.LiveView') -c Release
if($LASTEXITCODE -ne 0){throw 'Module build failed'}
$module=Join-Path $package 'Modules'
Remove-Item -LiteralPath $package -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $module | Out-Null
Copy-Item -LiteralPath (Join-Path $workspace 'module\Voxta.Modules.LiveView\bin\Release\net10.0\Voxta.Modules.LiveView.dll') -Destination $module -Force
Copy-Item -LiteralPath (Join-Path $workspace 'module\Install.ps1'),(Join-Path $workspace 'module\README.md'),(Join-Path $workspace 'LICENSE') -Destination $package -Force
Copy-Item -LiteralPath (Join-Path $workspace 'module\Voxta.Modules.LiveView\bin\Release\net10.0\Voxta.Modules.LiveView.dll') -Destination (Join-Path $package 'Voxta.Modules.LiveView.dll') -Force
Compress-Archive -Path (Join-Path $package '*') -DestinationPath "$package.zip" -Force
Write-Output "Module package: $package"
