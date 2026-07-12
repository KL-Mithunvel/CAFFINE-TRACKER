# Creates a "Caffeine Tracker" desktop shortcut that launches the app
# silently (no console window) via the project's own virtualenv.
# Run once, from anywhere: powershell -File scripts\create_desktop_shortcut.ps1

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$MainScript = Join-Path $ProjectRoot "main.py"

if (-not (Test-Path $PythonW)) {
    Write-Error "Virtualenv not found at $PythonW. Run start_tracker.bat once first to create it."
    exit 1
}

$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Caffeine Tracker.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$MainScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = $PythonW
$Shortcut.Description = "Caffeine Tracker"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
