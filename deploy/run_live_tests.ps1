$ErrorActionPreference = 'Continue'
$API = "https://overtone-v2-api-4idrhaffca-uc.a.run.app"
$PRESENTER = "https://overtone-v2-presenter-4idrhaffca-uc.a.run.app"
$DASHBOARD = "https://overtone-v2-dashboard-4idrhaffca-uc.a.run.app"
$adminKey = ((gcloud run services describe overtone-backend --region=us-central1 --format=json | ConvertFrom-Json).spec.template.spec.containers[0].env | Where-Object { $_.name -eq 'ADMIN_API_KEY' }).value
$H = @{ "X-API-Key" = $adminKey }
$results = New-Object System.Collections.Generic.List[object]

function Add-Result($test, $ok, $detail) {
  $d = "$detail"
  if ($d.Length -gt 500) { $d = $d.Substring(0, 500) }
  $results.Add([pscustomobject]@{ test = $test; ok = [bool]$ok; detail = $d })
  $mark = if ($ok) { 'PASS' } else { 'FAIL' }
  Write-Host "[$mark] $test :: $d"
}

# health / frontends
try {
  $r = Invoke-RestMethod "$API/health"
  Add-Result 'health' ($r.status -eq 'ok') ($r | ConvertTo-Json -Compress)
} catch { Add-Result 'health' $false $_.Exception.Message }

foreach ($pair in @(@('presenter', $PRESENTER), @('dashboard', $DASHBOARD))) {
  try {
    $resp = Invoke-WebRequest -Uri $pair[1] -UseBasicParsing -TimeoutSec 30
    Add-Result $pair[0] ($resp.StatusCode -eq 200) "HTTP $($resp.StatusCode)"
  } catch { Add-Result $pair[0] $false $_.Exception.Message }
}

# auth
try {
  $r = Invoke-RestMethod -Method POST "$API/auth/admin" -Headers $H -ContentType 'application/json' -Body '{}'
  Add-Result 'auth_admin' ($r.ok -eq $true) ($r | ConvertTo-Json -Compress)
} catch { Add-Result 'auth_admin' $false $_.Exception.Message }

try {
  $null = Invoke-RestMethod -Method POST "$API/auth/admin" -Headers @{ 'X-API-Key' = 'bad' } -ContentType 'application/json' -Body '{}'
  Add-Result 'auth_reject' $false 'expected 401'
} catch {
  $code = 0
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  Add-Result 'auth_reject' ($code -eq 401) "HTTP $code"
}

# agents / customers / list
try {
  $r = Invoke-RestMethod "$API/api/v1/agents" -Headers $H
  Add-Result 'agents_list' $true (($r | ConvertTo-Json -Compress).Substring(0, [Math]::Min(200, (($r | ConvertTo-Json -Compress).Length))))
} catch { Add-Result 'agents_list' $false $_.Exception.Message }

try {
  $r = Invoke-RestMethod "$API/api/v1/agents/default/versions" -Headers $H
  Add-Result 'agents_version' ($null -ne $r) ("count=" + @($r).Count)
} catch { Add-Result 'agents_version' $false $_.Exception.Message }

$custKey = $null
try {
  $body = @{ name = ("live-test-" + (Get-Date -Format 'HHmmss')) } | ConvertTo-Json
  $r = Invoke-RestMethod -Method POST "$API/api/v1/customers" -Headers $H -ContentType 'application/json' -Body $body
  $custKey = $r.api_key
  Add-Result 'customers' ($null -ne $r.id) ("id=" + $r.id)
} catch { Add-Result 'customers' $false $_.Exception.Message }

try {
  $r = Invoke-RestMethod "$API/api/v1/presentations" -Headers $H
  Add-Result 'presentations_list' $true ("count=" + @($r).Count)
} catch { Add-Result 'presentations_list' $false $_.Exception.Message }

# upload
$pdf = "D:\Products\overtone-meeting-assistant\docs\outbound\Overtone_Architecture_Overview.pdf"
Write-Host "Uploading $pdf"
$presentationId = $null
try {
  $upload = curl.exe -s -w "`nHTTP:%{http_code}" -X POST "$API/api/v1/presentations" -H "X-API-Key: $adminKey" -F "file=@$pdf"
  $lines = $upload -split "`n"
  $httpLine = ($lines | Where-Object { $_ -like 'HTTP:*' } | Select-Object -Last 1)
  $jsonLine = ($lines | Where-Object { $_ -notlike 'HTTP:*' }) -join "`n"
  $meta = $jsonLine | ConvertFrom-Json
  $presentationId = $meta.presentation_id
  Add-Result 'upload' ($null -ne $presentationId) ("id=$presentationId status=$($meta.status) $httpLine")
} catch {
  Add-Result 'upload' $false $_.Exception.Message
}

$final = $null
if ($presentationId) {
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 8
    try {
      $final = Invoke-RestMethod "$API/api/v1/presentations/$presentationId" -Headers $H
      Write-Host ("index poll {0}: status={1} pages={2} err={3}" -f ($i + 1), $final.status, $final.total_pages, $final.index_error)
      if ($final.status -in @('ready', 'failed')) { break }
    } catch {
      Write-Host ("index poll error: " + $_.Exception.Message)
    }
  }
  if ($final) {
    Add-Result 'index_job' ($final.status -eq 'ready') ("status=$($final.status) pages=$($final.total_pages) provider=$($final.metadata_provider) model=$($final.metadata_model) chunks=$($final.indexed_chunks) err=$($final.index_error)")
  } else {
    Add-Result 'index_job' $false 'no status'
  }

  if ($final -and $final.status -eq 'ready') {
    try {
      $img = Invoke-WebRequest -Uri "$API/api/v1/presentations/$presentationId/pages/1/image" -UseBasicParsing -TimeoutSec 30
      Add-Result 'page_image' (($img.StatusCode -eq 200) -and ($img.RawContentLength -gt 100)) ("HTTP $($img.StatusCode) bytes=$($img.RawContentLength)")
    } catch { Add-Result 'page_image' $false $_.Exception.Message }

    $meet = 'https://meet.google.com/aaa-bbbb-ccc'
    try {
      $launchBody = @{ meeting_url = $meet; presentation_id = $presentationId; bot_name = 'OvertoneV2Test'; agent_name = 'default' } | ConvertTo-Json
      $launch = Invoke-RestMethod -Method POST "$API/api/v1/sessions/launch" -Headers $H -ContentType 'application/json' -Body $launchBody
      Add-Result 'session_launch' ($null -ne $launch.session_id) ("session=$($launch.session_id) bot=$($launch.recall_bot_id) state=$($launch.state)")
      $sid = $launch.session_id
      Start-Sleep -Seconds 3
      try {
        $got = Invoke-RestMethod "$API/api/v1/sessions/$sid" -Headers $H
        Add-Result 'session_get' ($got.session_id -eq $sid) ("state=$($got.state) status=$($got.last_status_code)")
      } catch { Add-Result 'session_get' $false $_.Exception.Message }
      try {
        $left = Invoke-RestMethod -Method POST "$API/api/v1/sessions/$sid/leave" -Headers $H -ContentType 'application/json' -Body '{}'
        Add-Result 'session_leave' $true ($left | ConvertTo-Json -Compress)
      } catch { Add-Result 'session_leave' $false $_.Exception.Message }
    } catch {
      $msg = $_.Exception.Message
      if ($_.ErrorDetails.Message) { $msg = $_.ErrorDetails.Message }
      Add-Result 'session_launch' $false $msg
      Add-Result 'session_get' $false 'skipped'
      Add-Result 'session_leave' $false 'skipped'
    }
  } else {
    Add-Result 'page_image' $false 'skipped — index not ready'
    Add-Result 'session_launch' $false 'skipped — index not ready'
    Add-Result 'session_get' $false 'skipped'
    Add-Result 'session_leave' $false 'skipped'
  }
}

if ($custKey) {
  try {
    $r = Invoke-RestMethod "$API/api/v1/presentations" -Headers @{ 'X-API-Key' = $custKey }
    Add-Result 'customer_key_auth' $true ("presentations=" + @($r).Count)
  } catch { Add-Result 'customer_key_auth' $false $_.Exception.Message }
}

$outPath = 'D:\Products\overtone-meeting-assistant\v2\deploy\live-test-results.json'
$results | ConvertTo-Json -Depth 5 | Set-Content -Path $outPath -Encoding utf8
Write-Host ""
Write-Host "=== SUMMARY ==="
$results | ForEach-Object { Write-Host ("{0,-20} {1}" -f $_.test, $(if ($_.ok) { 'PASS' } else { 'FAIL' })) }
Write-Host "Wrote $outPath"
