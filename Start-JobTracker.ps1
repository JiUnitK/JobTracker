param(
    [int]$Port = 8765,
    [string]$HostName = "127.0.0.1",
    [switch]$NoOpen,
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "    $Message"
}

function Find-SystemPython {
    $commands = @(
        @{ File = "py"; Args = @("-3.12") },
        @{ File = "py"; Args = @("-3") },
        @{ File = "python"; Args = @() },
        @{ File = "python3"; Args = @() }
    )

    foreach ($command in $commands) {
        $executable = Get-Command $command.File -ErrorAction SilentlyContinue
        if ($null -eq $executable) {
            continue
        }

        try {
            $versionText = & $command.File @($command.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($versionText)) {
                continue
            }

            $parts = $versionText.Trim().Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
                return $command
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Install-PythonWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($null -eq $winget) {
        Write-Host ""
        Write-Host "Python 3.12+ is required, but Python and winget were not found." -ForegroundColor Yellow
        Write-Host "Install Python from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
        return $false
    }

    Write-Host ""
    $answer = Read-Host "Python 3.12+ was not found. Install Python 3.12 now using winget? [Y/N]"
    if ($answer.Trim().ToLowerInvariant() -notin @("y", "yes")) {
        Write-Host "Python is required. Install Python 3.12+ and run Start-JobTracker.bat again." -ForegroundColor Yellow
        return $false
    }

    Write-Step "Installing Python 3.12 with winget"
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget could not install Python. Install Python manually and run this launcher again." -ForegroundColor Red
        return $false
    }

    return $true
}

function Get-VenvPythonPath {
    param([string]$Root)
    return Join-Path $Root ".venv\Scripts\python.exe"
}

function Ensure-Venv {
    param(
        [hashtable]$PythonCommand,
        [string]$Root
    )

    $venvPython = Get-VenvPythonPath -Root $Root
    if ((Test-Path $venvPython) -and -not $Refresh) {
        Write-Info "Using existing virtual environment."
        return $venvPython
    }

    if ((Test-Path (Join-Path $Root ".venv")) -and $Refresh) {
        Write-Info "Refreshing dependencies in the existing virtual environment."
    }
    else {
        Write-Step "Creating virtual environment"
        & $PythonCommand.File @($PythonCommand.Args + @("-m", "venv", ".venv"))
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create .venv."
        }
    }

    return $venvPython
}

function Install-Project {
    param([string]$PythonPath)

    $stampPath = Join-Path ".venv" ".jobtracker-install-stamp"
    $projectFiles = @("pyproject.toml", "README.md")
    $latestProjectWrite = ($projectFiles | Where-Object { Test-Path $_ } | ForEach-Object {
        (Get-Item $_).LastWriteTimeUtc
    } | Measure-Object -Maximum).Maximum

    $needsInstall = $Refresh -or -not (Test-Path $stampPath)
    if (-not $needsInstall -and $latestProjectWrite) {
        $needsInstall = (Get-Item $stampPath).LastWriteTimeUtc -lt $latestProjectWrite
    }

    if (-not $needsInstall) {
        Write-Info "Dependencies already installed."
        return
    }

    Write-Step "Installing JobTracker dependencies"
    & $PythonPath -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Could not upgrade pip."
    }

    & $PythonPath -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install JobTracker."
    }

    New-Item -Path $stampPath -ItemType File -Force | Out-Null
}

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $values[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $values
}

function Ensure-BraveKey {
    param([string]$EnvPath)

    if ($env:BRAVE_SEARCH_API_KEY) {
        Write-Info "Using BRAVE_SEARCH_API_KEY from the current environment."
        return
    }

    $envValues = Read-DotEnv -Path $EnvPath
    if ($envValues.ContainsKey("BRAVE_SEARCH_API_KEY") -and $envValues["BRAVE_SEARCH_API_KEY"]) {
        Write-Info "Found BRAVE_SEARCH_API_KEY in .env."
        return
    }

    Write-Step "Configure Brave Search"
    Write-Host "Instant job search requires a Brave Search API key."
    Write-Host "Create one at: https://api.search.brave.com/"
    $key = Read-Host "Paste BRAVE_SEARCH_API_KEY"
    if ([string]::IsNullOrWhiteSpace($key)) {
        throw "BRAVE_SEARCH_API_KEY is required for instant job search."
    }

    Set-DotEnvValue -Path $EnvPath -Key "BRAVE_SEARCH_API_KEY" -Value $key.Trim()
    Write-Info "Saved BRAVE_SEARCH_API_KEY to .env."
}

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $line = "$Key=$Value"
    if (-not (Test-Path $Path)) {
        Set-Content -Path $Path -Value $line -Encoding UTF8
        return
    }

    $lines = @(Get-Content $Path)
    $updated = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\s*$([regex]::Escape($Key))\s*=") {
            $lines[$index] = $line
            $updated = $true
            break
        }
    }

    if ($updated) {
        Set-Content -Path $Path -Value $lines -Encoding UTF8
        return
    }

    if (($lines -join "").Trim().Length -gt 0) {
        Add-Content -Path $Path -Value ""
    }
    Add-Content -Path $Path -Value $line
}

function Test-PortAvailable {
    param(
        [string]$HostName,
        [int]$Port
    )

    $listener = $null
    try {
        $address = [System.Net.IPAddress]::Parse($HostName)
        $listener = [System.Net.Sockets.TcpListener]::new($address, $Port)
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Find-OpenPort {
    param(
        [string]$HostName,
        [int]$StartPort
    )

    for ($candidate = $StartPort; $candidate -lt ($StartPort + 50); $candidate++) {
        if (Test-PortAvailable -HostName $HostName -Port $candidate) {
            return $candidate
        }
    }
    throw "Could not find an open local port starting at $StartPort."
}

function Wait-ForServer {
    param(
        [string]$Url,
        [System.Diagnostics.Process]$Process
    )

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($Process.HasExited) {
            throw "JobTracker server exited before it was ready."
        }

        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "Timed out waiting for JobTracker at $Url."
}

try {
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $root

    Write-Host "JobTracker Launcher" -ForegroundColor Green
    Write-Info "Project: $root"

    Write-Step "Checking Python"
    $pythonCommand = Find-SystemPython
    if ($null -eq $pythonCommand) {
        if (Install-PythonWithWinget) {
            $pythonCommand = Find-SystemPython
        }
    }
    if ($null -eq $pythonCommand) {
        throw "Python 3.12+ is required before JobTracker can start."
    }
    Write-Info "Python is available."

    $venvPython = Ensure-Venv -PythonCommand $pythonCommand -Root $root
    Install-Project -PythonPath $venvPython
    Ensure-BraveKey -EnvPath (Join-Path $root ".env")

    $actualPort = Find-OpenPort -HostName $HostName -StartPort $Port
    if ($actualPort -ne $Port) {
        Write-Info "Port $Port is busy; using $actualPort instead."
    }

    $url = "http://$($HostName):$actualPort"
    Write-Step "Starting JobTracker"
    Write-Info "URL: $url"

    $server = Start-Process `
        -FilePath $venvPython `
        -ArgumentList @("-m", "jobtracker", "web", "--host", $HostName, "--port", "$actualPort") `
        -WorkingDirectory $root `
        -PassThru `
        -NoNewWindow

    Wait-ForServer -Url $url -Process $server

    if (-not $NoOpen) {
        Write-Info "Opening browser."
        Start-Process $url
    }

    Write-Host ""
    Write-Host "JobTracker is running at $url" -ForegroundColor Green
    Write-Host "Close this window or press Ctrl+C to stop the server."
    Wait-Process -Id $server.Id
}
catch {
    Write-Host ""
    Write-Host "JobTracker could not start:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
    }
}
