param(
    [ValidateSet('chat','admin')][string]$Mode = 'chat',
    [string]$Profile = '',
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
        $taskIdentityArgs = @('-X','utf8','-B','-m','research_ideation.admin','--data-root',$DataRoot,'current')
        if ($Profile) { $taskIdentityArgs += @('--profile',$Profile) }
        $taskIdentityOutput = & $taskRuntime.hermes_python @taskIdentityArgs
        if ($LASTEXITCODE -ne 0) { throw 'Select your single-user profile first with the setup command; see QUICKSTART.md.' }
        $taskIdentity = (($taskIdentityOutput -join "`n") | ConvertFrom-Json).data
        $Profile = $taskIdentity.profile
        $taskProfileHome = [System.IO.DirectoryInfo]::new($taskIdentity.home)
        $env:HERMES_HOME = if ($Profile -eq 'default') { $taskIdentity.home } else { $taskProfileHome.Parent.Parent.FullName }
        if ($taskRuntime.hermes_source) {
            $env:HERMES_PYTHON_SRC_ROOT = $taskRuntime.hermes_source
            $env:PYTHONPATH = $taskRuntime.hermes_source
            Set-Location -LiteralPath $taskRuntime.hermes_source
        }
        & $taskRuntime.hermes_python -X utf8 -B -m hermes_cli.main -p $Profile chat @Arguments
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
