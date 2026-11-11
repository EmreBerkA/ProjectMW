@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ProjectMW.spec || exit /b 1
copy /y LICENSE dist\ProjectMW\LICENSE.txt >nul
copy /y THIRD_PARTY_NOTICES.txt dist\ProjectMW\ >nul
xcopy /y /i /q licenses dist\ProjectMW\licenses >nul
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
"%ISCC%" installer.iss || exit /b 1
for /f %%v in ('.venv\Scripts\python.exe -c "from paths import APP_VERSION; print(APP_VERSION)"') do set VERSION=%%v
del /q dist\ProjectMW-%VERSION%-Portable.zip 2>nul
tar -a -c -f dist\ProjectMW-%VERSION%-Portable.zip -C dist ProjectMW || exit /b 1
powershell -NoProfile -Command "Get-FileHash dist\ProjectMW-%VERSION%-*.* -Algorithm SHA256 | ForEach-Object { $_.Hash.ToLower() + '  ' + (Split-Path $_.Path -Leaf) } | Set-Content -Encoding ascii dist\SHA256SUMS.txt"
type dist\SHA256SUMS.txt
