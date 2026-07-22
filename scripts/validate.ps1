$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path (Get-Location) "src"
python -m unittest discover -s tests
