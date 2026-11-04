# Phase 0 backup procedure

Use this procedure before changing application services or database behavior.
It does not run migration or change the database schema.

## 1. Stop the desktop application

Close every PigSkin AI Studio window. Confirm that no team member is creating or
editing a case. This keeps the SQL backup and `case_images` copy at the same
logical point in time.

Do not copy `C:\Users\ADMIN\PigSkinAI.mdf` or
`C:\Users\ADMIN\PigSkinAI_log.ldf` while LocalDB has them attached.

## 2. Create a SQL Server backup

Run PowerShell from:

```text
C:\Users\ADMIN\Downloads\pigskin_studio_nam
```

Create a timestamped destination:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $env:USERPROFILE "Documents\PigSkinBackups\$stamp"
New-Item -ItemType Directory -Path $backupDir
$env:PIGSKIN_BACKUP_FILE = Join-Path $backupDir 'PigSkinAI.bak'
```

Create the native SQL backup with the project interpreter:

```powershell
@'
import os
import pyodbc

target = os.environ['PIGSKIN_BACKUP_FILE']
connection = pyodbc.connect(
    r'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=(localdb)\MSSQLLocalDB;DATABASE=master;'
    r'Trusted_Connection=yes;Encrypt=no;',
    autocommit=True,
    timeout=10,
)
try:
    connection.cursor().execute(
        'DECLARE @target NVARCHAR(4000)=?; '
        'BACKUP DATABASE [PigSkinAI] TO DISK=@target '
        'WITH COPY_ONLY, INIT, CHECKSUM, STATS=10',
        target,
    )
finally:
    connection.close()
print(target)
'@ | .\.venv\Scripts\python.exe -
```

`COPY_ONLY` avoids disturbing a future differential-backup chain. The command
writes a backup file but does not modify application rows or schema.

## 3. Copy the image archive and legacy SQLite safety copy

```powershell
Copy-Item -LiteralPath '.\pigskin_studio_nam\case_images' `
    -Destination (Join-Path $backupDir 'case_images') -Recurse
Copy-Item -LiteralPath '.\pigskin_studio_nam\pigskin_history.db' `
    -Destination (Join-Path $backupDir 'pigskin_history.db')
```

Never replace or delete the source files after copying them.

## 4. Verify the SQL backup

```powershell
@'
import os
import pyodbc

target = os.environ['PIGSKIN_BACKUP_FILE']
connection = pyodbc.connect(
    r'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=(localdb)\MSSQLLocalDB;DATABASE=master;'
    r'Trusted_Connection=yes;Encrypt=no;',
    autocommit=True,
    timeout=10,
)
try:
    connection.cursor().execute(
        'DECLARE @target NVARCHAR(4000)=?; '
        'RESTORE VERIFYONLY FROM DISK=@target WITH CHECKSUM',
        target,
    )
finally:
    connection.close()
print('Backup verification completed successfully.')
'@ | .\.venv\Scripts\python.exe -
```

Create a checksum manifest for the complete snapshot:

```powershell
Get-ChildItem -LiteralPath $backupDir -File -Recurse |
    Get-FileHash -Algorithm SHA256 |
    Export-Csv -NoTypeInformation -Encoding UTF8 `
        -LiteralPath (Join-Path $backupDir 'SHA256SUMS.csv')
```

Keep at least one copy outside the development folder. A backup is accepted only
after `RESTORE VERIFYONLY` succeeds and the image folder is present.
