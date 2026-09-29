param([switch]$Refresh)
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$origin = "https://wiki.mysqil.com"
$userAgent = "Mozilla/5.0 (compatible; KekeZhushouLocalImporter/1.0)"
$timestamp = [DateTime]::UtcNow.ToString("o")

function Get-Page([string]$Url) {
    Invoke-WebRequest -Uri $Url -TimeoutSec 45 -UseBasicParsing -UserAgent $userAgent
}

function Save-Text([string]$Path, [string]$Text) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

$indexResponse = Get-Page "$origin/weapons/"
if ($indexResponse.StatusCode -ne 200) { throw "Unexpected weapons index status: $($indexResponse.StatusCode)" }
$indexPath = Join-Path $root "data\mysqil\weapons\raw\index.html"
Save-Text $indexPath $indexResponse.Content
$declaredCount = [regex]::Match($indexResponse.Content, '共\s*(\d+)\s*件弧盘')
if (-not $declaredCount.Success) { throw "Could not read arc-drive count from the source index." }
$expectedCount = [int]$declaredCount.Groups[1].Value

$items = @()
foreach ($match in [regex]::Matches($indexResponse.Content, '(?is)<a\b[^>]*class="[^"]*\bweapon-item\b[^"]*"[^>]*>.*?</a>')) {
    $anchor = $match.Value
    $href = [regex]::Match($anchor, '(?i)\bhref="/weapons/([^"/?#]+)')
    if (-not $href.Success) { continue }
    $slug = [Uri]::UnescapeDataString($href.Groups[1].Value)
    if ($slug -notmatch '^[a-z0-9-]+$') { throw "Unsafe weapon slug: $slug" }
    $plain = [Net.WebUtility]::HtmlDecode([regex]::Replace($anchor, '(?is)<[^>]+>', ' ')) -replace '\s+', ' '
    $grade = [regex]::Match($plain, '(?:^|\s)(S|A|B)(?:\s|$)').Groups[1].Value
    $type = [regex]::Match($plain, '(聚合|固态|液态|气态|等离子)(?:类)?\s*$').Groups[1].Value
    $name = [regex]::Replace($plain, '\s+[SAB]\s+(?:聚合|固态|液态|气态|等离子)\s*$', '').Trim()
    if (-not $name -or $grade -notin @('S','A','B') -or -not $type) { throw "Could not parse index metadata: $plain" }
    $items += [pscustomobject]@{ id = $slug; name = $name; rarity = $grade; type = $type; source_url = "$origin/weapons/$([Uri]::EscapeDataString($slug))/" }
}
if ($items.Count -ne $expectedCount) { throw "Source index declares $expectedCount arc drives but exposes $($items.Count) items. No roster was written." }

$assetTasks = @{}
foreach ($item in $items) {
    $pagePath = Join-Path $root "data\mysqil\weapons\$($item.id)\raw\page.html"
    if ((Test-Path -LiteralPath $pagePath) -and -not $Refresh) {
        $html = [IO.File]::ReadAllText($pagePath, [Text.Encoding]::UTF8)
        $downloaded = $false
    } else {
        $page = Get-Page $item.source_url
        if ($page.StatusCode -ne 200) { throw "HTTP $($page.StatusCode): $($item.source_url)" }
        $html = $page.Content
        Save-Text $pagePath $html
        $downloaded = $true
    }
    if ($html -notmatch [regex]::Escape($item.name)) { throw "Source page name mismatch: $($item.id)" }
    $item | Add-Member -NotePropertyName raw_page -NotePropertyValue "data/mysqil/weapons/$($item.id)/raw/page.html" -Force
    $item | Add-Member -NotePropertyName page_updated -NotePropertyValue $downloaded -Force
    $imageUrls = @([regex]::Matches($html, '(?i)\bsrc="(/images/weapons/[^"?#]+)"') | ForEach-Object { "$origin$($_.Groups[1].Value)" } | Select-Object -Unique)
    if ($imageUrls.Count -eq 0) { throw "No weapon image found on $($item.source_url)" }
    $item | Add-Member -NotePropertyName source_images -NotePropertyValue $imageUrls -Force
    foreach ($imageUrl in $imageUrls) {
        $filename = [IO.Path]::GetFileName(([Uri]$imageUrl).AbsolutePath)
        $assetPath = "data/resources/encyclopedia/weapons/$($item.id)/$filename"
        $target = [IO.Path]::GetFullPath((Join-Path $root ($assetPath -replace '/', '\')))
        if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Asset path escaped workspace: $target" }
        $assetTasks[$imageUrl] = [pscustomobject]@{ url = $imageUrl; target = $target; local_path = $assetPath; item_id = $item.id }
    }
    Write-Output "PAGE $($item.id) $(if ($downloaded) { 'downloaded' } else { 'cached' })"
}

$assetResults = @($assetTasks.Values | ForEach-Object -Parallel {
    $task = $_
    try {
        if ((Test-Path -LiteralPath $task.target) -and -not $using:refresh) {
            $bytes = [IO.File]::ReadAllBytes($task.target)
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $task.target) | Out-Null
            $response = Invoke-WebRequest -Uri $task.url -TimeoutSec 45 -UseBasicParsing -UserAgent $using:userAgent -OutFile $task.target -PassThru
            if ($response.StatusCode -ne 200 -or $response.Headers['Content-Type'] -notmatch '^image/') { throw "Unexpected image response: $($response.StatusCode) $($response.Headers['Content-Type'])" }
            $bytes = [IO.File]::ReadAllBytes($task.target)
        }
        $sha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([byte[]]$bytes)).ToLowerInvariant()
        [pscustomobject]@{ item_id = $task.item_id; source_url = $task.url; local_path = $task.local_path; sha256 = $sha; status = 'ok' }
    } catch {
        [pscustomobject]@{ item_id = $task.item_id; source_url = $task.url; local_path = $task.local_path; status = 'failed'; error = $_.Exception.Message }
    }
} -ThrottleLimit 4)
$failedAssets = @($assetResults | Where-Object status -eq 'failed')
if ($failedAssets.Count) { $failedAssets | ForEach-Object { Write-Warning "ASSET $($_.source_url): $($_.error)" }; throw "Failed to download $($failedAssets.Count) weapon images." }

foreach ($item in $items) {
    $item | Add-Member -NotePropertyName assets -NotePropertyValue @($assetResults | Where-Object item_id -eq $item.id | ForEach-Object { $_ | Select-Object source_url,local_path,sha256 }) -Force
    $item.PSObject.Properties.Remove('source_images')
    $item.PSObject.Properties.Remove('page_updated')
}
$manifest = [ordered]@{
    source = 'Mysqil · 环世全鉴'
    source_index = "$origin/weapons/"
    source_license = 'CC BY-NC-SA 4.0'
    source_author = 'Matsuzaka Yuki'
    retrieved_at = $timestamp
    expected_count = $expectedCount
    items = $items
}
$rosterPath = Join-Path $root "data\mysqil\weapons\roster.json"
Save-Text $rosterPath (ConvertTo-Json -InputObject $manifest -Depth 12)
Write-Output "SUMMARY items=$($items.Count) pages=$($items.Count) images=$($assetResults.Count) failures=$($failedAssets.Count)"
