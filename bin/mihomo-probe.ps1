#Requires -Version 7
<#
.SYNOPSIS
  Measure how a Mihomo proxy entry answers delay tests, in two phases:
  a burst (probes a few seconds apart, connections stay warm) and after-idle
  (each probe preceded by an idle gap longer than a typical web server's 75 s
  keepalive). The method and how to read it: skills/delay-probe/SKILL.md.

.EXAMPLE
  # 1. Find the exact name of the entry (optionally narrowed by a regex)
  mihomo-probe.ps1 -List -Match "xHTTP|Hysteria2"
  # 2. Measure, labelling the run with what the server runs now
  mihomo-probe.ps1 -Proxy "XX-1 xHTTP" -Label grpc
  # A two-minute smoke run
  mihomo-probe.ps1 -Proxy "XX-1 xHTTP" -BurstProbes 3 -IdleProbes 0

.NOTES
  Talks to Mihomo's external controller (GET /proxies/{name}/delay), either
  over a Windows named pipe — what Clash Verge-family clients use; found
  automatically — or over TCP with -Controller. The secret is asked for at
  start and never written anywhere (-NoSecret skips the prompt when the
  controller has none). Results go to a CSV in the current directory; the
  summary is printed at the end. Entry names can identify a fleet — keep the
  CSV and the output out of anything public.
#>
param(
    [string]$Controller = "http://127.0.0.1:9090",
    [string]$Pipe,
    [string]$Proxy,
    [string]$Label = "run",
    [switch]$List,
    [string]$Match = "",
    [switch]$NoSecret,
    [int]$BurstProbes = 30,
    [int]$BurstGapSeconds = 3,
    [int]$IdleProbes = 10,
    [int]$IdleGapSeconds = 90,
    [int]$TimeoutMs = 5000,
    [string]$Url = "http://www.gstatic.com/generate_204"
)

$ErrorActionPreference = "Stop"

# --- where the controller is ------------------------------------------------
# A pipe is used when named, or when no -Controller was given and a pipe whose
# name mentions mihomo exists.
if (-not $Pipe -and -not $PSBoundParameters.ContainsKey('Controller')) {
    $found = [System.IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -match 'mihomo' } | Select-Object -First 1
    if ($found) { $Pipe = $found }
}
if ($Pipe) { $Pipe = $Pipe -replace '^\\\\\.\\pipe\\', '' }
Write-Host ("Controller: " + $(if ($Pipe) { "named pipe \\.\pipe\$Pipe" } else { $Controller }))

$secret = ""
if (-not $NoSecret) {
    $secure = Read-Host -AsSecureString "Mihomo controller secret (Enter if none)"
    $secret = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

# GET <pathAndQuery> from the controller -> @{ Status; Body }. Over a pipe the
# request is HTTP/1.0 with Connection: close, so the response is never chunked
# and ends when the server closes the pipe.
function Invoke-Controller([string]$pathAndQuery, [int]$timeoutMs) {
    if ($Pipe) {
        $stream = [System.IO.Pipes.NamedPipeClientStream]::new('.', $Pipe, [System.IO.Pipes.PipeDirection]::InOut, [System.IO.Pipes.PipeOptions]::Asynchronous)
        try {
            $stream.Connect(5000)
            $auth = if ($secret) { "Authorization: Bearer $secret`r`n" } else { "" }
            $req = [Text.Encoding]::UTF8.GetBytes("GET $pathAndQuery HTTP/1.0`r`nHost: localhost`r`n$auth" + "Connection: close`r`n`r`n")
            $stream.Write($req, 0, $req.Length)
            $stream.Flush()
            $buffer = [System.IO.MemoryStream]::new()
            if (-not $stream.CopyToAsync($buffer).Wait($timeoutMs)) { throw "controller did not answer within $timeoutMs ms" }
            $raw = [Text.Encoding]::UTF8.GetString($buffer.ToArray())
        } finally {
            $stream.Dispose()
        }
        $split = $raw.IndexOf("`r`n`r`n")
        if ($split -lt 0) { throw "malformed controller response" }
        return [pscustomobject]@{ Status = [int]($raw.Substring(0, $split).Split(' ')[1]); Body = $raw.Substring($split + 4) }
    }
    $headers = @{}
    if ($secret) { $headers["Authorization"] = "Bearer $secret" }
    $r = Invoke-WebRequest -Uri ($Controller + $pathAndQuery) -Headers $headers -SkipHttpErrorCheck -TimeoutSec ([math]::Ceiling($timeoutMs / 1000))
    return [pscustomobject]@{ Status = [int]$r.StatusCode; Body = $r.Content }
}

if ($List) {
    $r = Invoke-Controller "/proxies" 10000
    if ($r.Status -ne 200) { throw "controller answered $($r.Status): $($r.Body)" }
    # Proxies only: groups (Selector, URLTest, LoadBalance, …) have a member list.
    ($r.Body | ConvertFrom-Json).proxies.PSObject.Properties |
        Where-Object { -not $_.Value.all -and $_.Name -match $Match } |
        ForEach-Object { "{0,-12} {1}" -f $_.Value.type, $_.Name } | Sort-Object
    return
}
if (-not $Proxy) { throw "Pass -Proxy with the exact entry name (see -List)." }

$probePath = "/proxies/$([uri]::EscapeDataString($Proxy))/delay?timeout=$TimeoutMs&url=$([uri]::EscapeDataString($Url))"
$out = Join-Path (Get-Location) ("mihomo-probe-{0}-{1}.csv" -f $Label, (Get-Date -Format "yyyyMMdd-HHmmss"))
$rows = New-Object System.Collections.Generic.List[object]

function Probe([string]$phase, [int]$n) {
    $t = Get-Date
    try {
        $r = Invoke-Controller $probePath ($TimeoutMs + 5000)
        $json = $r.Body | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($r.Status -eq 200 -and $json.delay) {
            $row = [pscustomobject]@{ time = $t.ToString("s"); phase = $phase; n = $n; ok = $true; delay_ms = [int]$json.delay; error = "" }
        } else {
            $msg = if ($json.message) { $json.message } else { "HTTP $($r.Status)" }
            $row = [pscustomobject]@{ time = $t.ToString("s"); phase = $phase; n = $n; ok = $false; delay_ms = $null; error = $msg }
        }
    } catch {
        $row = [pscustomobject]@{ time = $t.ToString("s"); phase = $phase; n = $n; ok = $false; delay_ms = $null; error = $_.Exception.Message }
    }
    $rows.Add($row)
    $row | Export-Csv -Path $out -Append -NoTypeInformation -Encoding UTF8
    Write-Host ("{0} {1,-10} #{2,-3} {3}" -f $row.time, $phase, $n, $(if ($row.ok) { "$($row.delay_ms) ms" } else { "FAIL  $($row.error)" }))
}

Write-Host "Label '$Label' -> $out"
Write-Host "Burst: $BurstProbes probes, ${BurstGapSeconds}s apart"
for ($i = 1; $i -le $BurstProbes; $i++) { Probe "burst" $i; Start-Sleep -Seconds $BurstGapSeconds }

Write-Host "After-idle: $IdleProbes probes, each after ${IdleGapSeconds}s of silence (~$([math]::Round($IdleProbes * $IdleGapSeconds / 60)) min)"
for ($i = 1; $i -le $IdleProbes; $i++) { Start-Sleep -Seconds $IdleGapSeconds; Probe "after-idle" $i }

function Summ($phase) {
    $p = $rows | Where-Object { $_.phase -eq $phase }
    $ok = @($p | Where-Object { $_.ok } | ForEach-Object { $_.delay_ms } | Sort-Object)
    $med = if ($ok.Count) { $ok[[int][math]::Floor(($ok.Count - 1) / 2)] } else { "-" }
    $p90 = if ($ok.Count) { $ok[[int][math]::Floor(($ok.Count - 1) * 0.9)] } else { "-" }
    [pscustomobject]@{ label = $Label; phase = $phase; probes = @($p).Count; failed = @($p | Where-Object { -not $_.ok }).Count; median_ms = $med; p90_ms = $p90 }
}
Write-Host ""
@(Summ "burst"; Summ "after-idle") | Format-Table -AutoSize
