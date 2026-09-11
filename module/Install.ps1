param(
 [Parameter(Mandatory=$true)][string]$VoxtaPath,
 [switch]$Uninstall
)
$ErrorActionPreference='Stop'
$destination=[IO.Path]::GetFullPath($VoxtaPath)
if(!(Test-Path -LiteralPath (Join-Path $destination 'Voxta.Server.exe'))){throw 'Select the folder containing Voxta.Server.exe'}
$dll=Join-Path $destination 'Modules\Voxta.Modules.LiveView.dll'
if($Uninstall){
 if(Test-Path -LiteralPath $dll){Remove-Item -LiteralPath $dll -Force}
 Write-Output 'Module removed. Restart Voxta. Runtime, models and settings were retained for reinstall.'
 exit
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Modules\Voxta.Modules.LiveView.dll') -Destination $dll -Force
$content=Join-Path $destination 'Data\LiveView'
foreach($name in @('portrait_worker.py','models.py')){
 Remove-Item -LiteralPath (Join-Path $content "backend\$name") -Force -ErrorAction SilentlyContinue
}
Write-Output 'Installed Persona Live View. Restart Voxta, add Persona Live View in Services, and enable persona_live_view in the chat augmentations. The first Live View start downloads its module-owned dependencies and model files through Voxta managed Python.'
