# One-Click Setup for Code Knowledge Chain (Windows PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$ScriptDir\scripts\setup.py" @args
