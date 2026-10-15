$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$environment = Join-Path $root '.venv'
$python = Join-Path $environment 'python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    New-Item -ItemType Directory -Path $environment -Force | Out-Null
    $archive = Join-Path $environment 'python-3.7.9-embed-amd64.zip'
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip' -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $environment -Force
    Remove-Item -LiteralPath $archive
}
$pathFile = Join-Path $environment 'python37._pth'
[IO.File]::WriteAllLines($pathFile, @('python37.zip', '.', 'Lib/site-packages', 'import site'), [Text.UTF8Encoding]::new($false))
$bootstrap = Join-Path $environment 'get-pip.py'
if (-not (Test-Path -LiteralPath $bootstrap)) {
    Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/pip/3.7/get-pip.py' -OutFile $bootstrap
}
& $python $bootstrap 'pip==24.0' 'setuptools==67.8.0' 'wheel==0.42.0' --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Legacy pip bootstrap failed' }
& $python -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements-legacy.txt')
if ($LASTEXITCODE -ne 0) { throw 'Legacy dependency installation failed' }
& $python -c 'import sys, sysconfig, pandas, simpy, xlrd, openpyxl, matplotlib; assert sys.version_info[:3] == (3, 7, 9); assert pandas.__version__ == "0.24.2"; print(sys.executable); print(sys.version); print(sysconfig.get_platform()); print("pandas", pandas.__version__, "SimPy", simpy.__version__)'
if ($LASTEXITCODE -ne 0) { throw 'Legacy environment verification failed' }
Write-Output 'Local legacy environment ready. Use .venv/python.exe explicitly; no activation or system Python changes are required.'