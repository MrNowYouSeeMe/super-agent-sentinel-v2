# Configure OpenAI locally for SuperAgent Sentinel V2.
# The API key is written only to E:\superagent-sentinel-v2\.env, which is Git-ignored.

$ErrorActionPreference = "Stop"
$Project = "E:\superagent-sentinel-v2"
$EnvPath = Join-Path $Project ".env"

if (-not (Test-Path $Project)) {
    throw "Project folder not found: $Project"
}

$SecureKey = Read-Host "Paste your OpenAI API key (input hidden)" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)

try {
    $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($PlainKey)) {
        throw "API key cannot be empty."
    }

    $Model = Read-Host "OpenAI model [default: gpt-5-mini]"
    if ([string]::IsNullOrWhiteSpace($Model)) {
        $Model = "gpt-5-mini"
    }

    $Content = @"
OPENAI_ENABLED=true
OPENAI_MODEL=$Model
OPENAI_API_KEY=$PlainKey
SUPERAGENT_ENV=local
SUPERAGENT_LOG_LEVEL=INFO
"@

    $Encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($EnvPath, $Content, $Encoding)

    Write-Host "OpenAI local configuration saved to $EnvPath ✅" -ForegroundColor Green
    Write-Host "Restart start-all.ps1 before testing OpenAI explanations." -ForegroundColor Yellow
}
finally {
    if ($Pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
    Remove-Variable PlainKey -ErrorAction SilentlyContinue
}