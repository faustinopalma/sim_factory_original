param([switch]$VerifyOnly)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup_legacy.ps1 first.' }
if (-not $VerifyOnly) {
    & $python (Join-Path $PSScriptRoot 'build_examples.py') generate
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic generation failed' }
    $excel = New-Object -ComObject Excel.Application
    $book = $null
    try {
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        $excel.EnableEvents = $false
        $excel.AskToUpdateLinks = $false
        foreach ($scenario in @('01_baseline', '02_capacity')) {
            $path = Join-Path $root "examples/$scenario/sim_factory_inputs.xlsx"
            $book = $excel.Workbooks.Open($path, 0, $false)
            $excel.CalculateFullRebuild()
            $book.Save()
            $book.Close($false)
            $book = $null
        }
    } finally {
        if ($book) { $book.Close($false) }
        $excel.Quit()
    }
    & $python (Join-Path $PSScriptRoot 'build_examples.py') run
    if ($LASTEXITCODE -ne 0) { throw 'Original simulator execution or output validation failed' }
}
& $python (Join-Path $PSScriptRoot 'verify_examples.py')
if ($LASTEXITCODE -ne 0) { throw 'Synthetic example verification failed' }
& $python (Join-Path $PSScriptRoot 'build_examples.py') report
if ($LASTEXITCODE -ne 0) { throw 'Example chart generation failed' }