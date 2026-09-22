@echo off
setlocal
cd /d "%~dp0"

rem Use an existing SDK, including the x86 SDK installed on this PC.
set "DOTNET=dotnet"
where dotnet >nul 2>&1
if errorlevel 1 (
    if exist "%ProgramFiles(x86)%\dotnet\dotnet.exe" (
        set "DOTNET=%ProgramFiles(x86)%\dotnet\dotnet.exe"
    ) else if exist "%ProgramFiles%\dotnet\dotnet.exe" (
        set "DOTNET=%ProgramFiles%\dotnet\dotnet.exe"
    )
)
"%DOTNET%" --version >nul 2>&1
if errorlevel 1 (
    echo .NET SDK not found. Check installation and PATH.
    pause
    exit /b 1
)

echo Compiling Semaphore Tenant Configurator for win-x64 ...
"%DOTNET%" publish ".\src\SemaphoreTenantConfigurator.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -p:DebugType=none -p:DebugSymbols=false -o ".\dist\publish"
if errorlevel 1 (
    echo.
    echo BUILD FEHLGESCHLAGEN. Erste Fehlermeldung oben pruefen.
    pause
    exit /b 1
)
if not exist ".\dist\publish\SemaphoreTenantConfigurator.exe" (
    echo BUILD FEHLGESCHLAGEN: EXE nicht gefunden.
    pause
    exit /b 1
)
copy /y ".\dist\publish\SemaphoreTenantConfigurator.exe" ".\dist\SemaphoreTenantConfigurator.exe" >nul
if errorlevel 1 (
    echo BUILD FEHLGESCHLAGEN: EXE konnte nicht kopiert werden.
    pause
    exit /b 1
)
echo.
echo FERTIG: %~dp0dist\SemaphoreTenantConfigurator.exe
pause
