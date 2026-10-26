param(
    [ValidateSet('chat','admin','tests')][string]$Mode = 'chat',
    [string]$Profile = 'research-alice',
    [string]$DataRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'research-data'),
    [string[]]$Arguments = @()
)
$ErrorActionPreference = 'Stop'
$taskRuntimePath = Join-Path $DataRoot 'control\runtime.json'
if (-not (Test-Path -LiteralPath $taskRuntimePath)) { throw 'Initialize research-admin first; see README.md.' }
$taskRuntime = Get-Content -LiteralPath $taskRuntimePath -Raw -Encoding utf8 | ConvertFrom-Json
if (-not $taskRuntime.hermes_python) { throw 'Set hermes_python in the local administrator runtime.json or run the documented Python commands directly.' }
$taskSavedHome = $env:HERMES_HOME
$taskSavedSource = $env:HERMES_PYTHON_SRC_ROOT
$taskSavedPythonPath = $env:PYTHONPATH
Push-Location -LiteralPath $PSScriptRoot
try {
    if ($Mode -eq 'chat') {
        $env:HERMES_HOME = $taskRuntime.hermes_root
        if ($taskRuntime.hermes_source) {
            $env:HERMES_PYTHON_SRC_ROOT = $taskRuntime.hermes_source
            $env:PYTHONPATH = $taskRuntime.hermes_source
            Set-Location -LiteralPath $taskRuntime.hermes_source
        }
        & $taskRuntime.hermes_python -X utf8 -B -m hermes_cli.main -p $Profile chat @Arguments
    } elseif ($Mode -eq 'tests') {
        & $taskRuntime.hermes_python -X utf8 -B -m unittest discover -s tests -v
    } else {
        & $taskRuntime.hermes_python -X utf8 -B -m research_ideation.admin --data-root $DataRoot @Arguments
    }
    $taskExitCode = $LASTEXITCODE
} finally {
    $env:HERMES_HOME = $taskSavedHome
    $env:HERMES_PYTHON_SRC_ROOT = $taskSavedSource
    $env:PYTHONPATH = $taskSavedPythonPath
    Pop-Location
}
exit $taskExitCode
