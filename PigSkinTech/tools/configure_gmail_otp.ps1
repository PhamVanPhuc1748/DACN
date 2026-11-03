$ErrorActionPreference = 'Stop'

$sender = Read-Host 'Enter the Gmail address used as the sender'
if ($sender -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') {
    throw 'Enter a valid Gmail address. No settings were changed.'
}
if ([Environment]::GetEnvironmentVariable('PIGSKIN_SMTP_PASSWORD', 'User')) {
    throw 'SMTP is already configured for this Windows user. Refusing to overwrite the saved credential.'
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
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -replace '\s', ''
    $random.GetBytes($randomBytes)
    $pepper = [Convert]::ToBase64String($randomBytes)

    $settings = @{
        PIGSKIN_SMTP_HOST = 'smtp.gmail.com'
        PIGSKIN_SMTP_PORT = '587'
        PIGSKIN_SMTP_USER = $sender
        PIGSKIN_SMTP_FROM = $sender
        PIGSKIN_SMTP_PASSWORD = $password
        PIGSKIN_OTP_PEPPER = $pepper
    }
    foreach ($name in $settings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'User')
    }
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

Write-Output 'Gmail SMTP settings and a fresh OTP pepper were saved to this Windows user profile.'
Write-Output 'Restart PigSkin AI Studio before requesting a verification code.'
