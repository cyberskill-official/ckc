# One-Click Cleanup for Code Knowledge Chain (Windows PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$ScriptDir\scripts\cleanup.py" @args
