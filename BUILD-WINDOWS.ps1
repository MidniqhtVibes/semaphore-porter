$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet) { throw 'Zum einmaligen Bauen ist das .NET 10 SDK erforderlich: https://dotnet.microsoft.com/download/dotnet/10.0' }
$ver = & dotnet --version
if ($LASTEXITCODE -ne 0 -or $ver -notmatch '^10\.') { throw "Bitte das .NET 10 SDK installieren (gefunden: $ver)." }
$project = Join-Path $PSScriptRoot 'src\SemaphoreTenantConfigurator.csproj'
$publish = Join-Path $PSScriptRoot 'dist\publish'
New-Item -ItemType Directory -Force -Path $publish | Out-Null
& dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:PublishTrimmed=false -p:DebugType=none -p:DebugSymbols=false -o $publish
if ($LASTEXITCODE -ne 0) { throw 'Publish fehlgeschlagen. Fehlermeldung oben ansehen.' }
$exe = Join-Path $publish 'SemaphoreTenantConfigurator.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Publish lief durch, aber die EXE fehlt.' }
Copy-Item -LiteralPath $exe -Destination (Join-Path $PSScriptRoot 'dist\SemaphoreTenantConfigurator.exe') -Force
Write-Host "FERTIG: $PSScriptRoot\dist\SemaphoreTenantConfigurator.exe" -ForegroundColor Green
Write-Host 'Die EXE direkt doppelklicken; keine Start.bat erforderlich.' -ForegroundColor Green
