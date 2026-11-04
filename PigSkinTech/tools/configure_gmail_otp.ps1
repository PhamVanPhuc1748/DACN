param(
    [string]$Sender = 'namt3869@gmail.com',
    [ValidateRange(1, 65535)]
    [int]$Port = 587,
    [switch]$UseSsl
)

$ErrorActionPreference = 'Stop'

try {
    $Sender = ([System.Net.Mail.MailAddress]$Sender).Address
}
catch {
    throw 'Sender must be a valid Gmail address. No settings were changed.'
}

$settingNames = @(
    'PIGSKIN_SMTP_HOST', 'PIGSKIN_SMTP_PORT', 'PIGSKIN_SMTP_USER',
    'PIGSKIN_SMTP_FROM', 'PIGSKIN_SMTP_PASSWORD', 'PIGSKIN_SMTP_SSL',
    'PIGSKIN_OTP_PEPPER'
)
$existing = @($settingNames | Where-Object {
    [Environment]::GetEnvironmentVariable($_, 'User')
})
if ($existing.Count -gt 0) {
    throw ('OTP/SMTP settings already exist for this Windows user: ' +
        ($existing -join ', ') + '. Refusing to overwrite them.')
}

$securePassword = Read-Host 'Enter the Gmail App Password (input is hidden)' -AsSecureString
if ($securePassword.Length -lt 12) {
    $securePassword.Dispose()
    throw 'The App Password looks too short. No settings were changed.'
}

$pointer = [IntPtr]::Zero
$password = $null
$randomBytes = New-Object byte[] 32
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$written = @()
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -replace '\s', ''
    if ($password.Length -lt 16) {
        throw 'The Gmail App Password looks too short. No settings were changed.'
    }
    $random.GetBytes($randomBytes)
    $pepper = [Convert]::ToBase64String($randomBytes)

    $settings = @{
        PIGSKIN_SMTP_HOST = 'smtp.gmail.com'
        PIGSKIN_SMTP_PORT = [string]$Port
        PIGSKIN_SMTP_USER = $Sender
        PIGSKIN_SMTP_FROM = $Sender
        PIGSKIN_SMTP_PASSWORD = $password
        PIGSKIN_OTP_PEPPER = $pepper
    }
    if ($UseSsl) {
        $settings.PIGSKIN_SMTP_SSL = '1'
    }
    foreach ($name in $settings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'User')
        $written += $name
    }
}
catch {
    foreach ($name in $written) {
        [Environment]::SetEnvironmentVariable($name, $null, 'User')
    }
    throw
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $securePassword.Dispose()
    $random.Dispose()
    [Array]::Clear($randomBytes, 0, $randomBytes.Length)
    $password = $null
    $pepper = $null
}

Write-Output "Gmail SMTP settings for $Sender and a fresh OTP pepper were saved to this Windows user profile."
Write-Output 'Restart PigSkin AI Studio before requesting a verification code.'
