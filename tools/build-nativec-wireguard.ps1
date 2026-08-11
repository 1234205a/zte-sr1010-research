param(
    [string]$WorkDir = "$env:USERPROFILE\Downloads\sr1010-wg-build",
    [string]$Zig = "$env:USERPROFILE\Downloads\portable-tools\zig-0.16.0\zig.exe"
)

$ErrorActionPreference = 'Stop'
$GoVersion = 'go1.26.5'
$GoArchive = "$GoVersion.windows-amd64.zip"
$GoSha256 = '97e6b2a833b6d89f9ff17d25419ac0a7e3b482a044e9ab18cdef834bd834fd38'
$WireGuardGoTag = '0.0.20250522'
$WireGuardToolsTag = 'v1.0.20260223'

New-Item -ItemType Directory -Force -Path $WorkDir, "$WorkDir\out" | Out-Null
$archivePath = "$WorkDir\$GoArchive"

if (-not (Test-Path $archivePath)) {
    @"
import urllib.request
urllib.request.urlretrieve('https://go.dev/dl/$GoArchive', r'$archivePath')
"@ | python -
}

$actual = (Get-FileHash -Algorithm SHA256 $archivePath).Hash.ToLowerInvariant()
if ($actual -ne $GoSha256) { throw "Go archive SHA-256 mismatch: $actual" }
if (-not (Test-Path "$WorkDir\go\bin\go.exe")) {
    Expand-Archive -LiteralPath $archivePath -DestinationPath $WorkDir
}

$env:GIT_SSL_BACKEND = 'openssl'
if (-not (Test-Path "$WorkDir\wireguard-go\.git")) {
    git clone --branch $WireGuardGoTag --depth 1 https://git.zx2c4.com/wireguard-go "$WorkDir\wireguard-go"
}
if (-not (Test-Path "$WorkDir\wireguard-tools\.git")) {
    git clone --branch $WireGuardToolsTag --depth 1 https://git.zx2c4.com/wireguard-tools "$WorkDir\wireguard-tools"
}

$env:GOROOT = "$WorkDir\go"
$env:GOPATH = "$WorkDir\gopath"
$env:GOCACHE = "$WorkDir\gocache"
$env:GOOS = 'linux'
$env:GOARCH = 'arm'
$env:GOARM = '7'
$env:CGO_ENABLED = '0'
Push-Location "$WorkDir\wireguard-go"
try {
    & "$WorkDir\go\bin\go.exe" build -trimpath -ldflags='-s -w -buildid=' -o "$WorkDir\out\wireguard-go-armv7" .
    if ($LASTEXITCODE) { throw "wireguard-go build failed: $LASTEXITCODE" }
} finally { Pop-Location }

if (-not (Test-Path $Zig)) { throw "Zig not found: $Zig" }
$src = "$WorkDir\wireguard-tools\src"
$sources = Get-ChildItem -LiteralPath $src -Filter '*.c' | ForEach-Object FullName
$zigArgs = @(
    'cc', '-target', 'arm-linux-musleabihf', '-mcpu=generic+v7a+vfp3d16',
    '-static', '-O2', '-std=gnu99', '-D_GNU_SOURCE',
    '-DRUNSTATEDIR="/var/run"', '-DWIREGUARD_TOOLS_VERSION="1.0.20260223"',
    "-isystem$src\uapi\linux", '-Wall', '-Wextra',
    '-o', "$WorkDir\out\wg-armv7-static"
) + $sources
& $Zig @zigArgs
if ($LASTEXITCODE) { throw "wireguard-tools build failed: $LASTEXITCODE" }

Get-Item "$WorkDir\out\wireguard-go-armv7", "$WorkDir\out\wg-armv7-static" |
    ForEach-Object {
        [pscustomobject]@{
            File = $_.FullName
            Bytes = $_.Length
            SHA256 = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant()
        }
    } | Format-Table -AutoSize

