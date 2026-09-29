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

$indexResponse = Get-Page "$origin/cassettes/"
if ($indexResponse.StatusCode -ne 200) { throw "Unexpected cassette index status: $($indexResponse.StatusCode)" }
$indexPath = Join-Path $root "data\mysqil\cassettes\raw\index.html"
Save-Text $indexPath $indexResponse.Content
$countMatch = [regex]::Match($indexResponse.Content, '共\s*(\d+)\s*套卡带')
if (-not $countMatch.Success) { throw "Could not read cassette count from the source index." }
$expectedCount = [int]$countMatch.Groups[1].Value

$items = @()
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($match in [regex]::Matches($indexResponse.Content, '(?is)<a\b[^>]*href="/cassettes/([^"/?#]+)"[^>]*>.*?</a>')) {
    $openingTag = [regex]::Match($match.Value, '(?is)^<a\b[^>]*>').Value
    $className = [regex]::Match($openingTag, '(?i)\bclass="([^"]*)"').Groups[1].Value
    if ($className -notmatch '\bbg-card\b' -or $className -notmatch '\boverflow-hidden\b') { continue }
    $slug = [Uri]::UnescapeDataString($match.Groups[1].Value)
    if ($slug -notmatch '^[\p{L}\p{N}-]+$') { throw "Unsafe cassette slug: $slug" }
    if (-not $seen.Add($slug)) { continue }
    $items += [pscustomobject]@{
        id = $slug
        name = ''
        source_url = "$origin/cassettes/$([Uri]::EscapeDataString($slug))"
    }
}
if ($items.Count -ne $expectedCount) {
    throw "Source index declares $expectedCount cassettes but exposes $($items.Count) distinct detail links. No roster was written."
}

$assetTasks = @{}
foreach ($item in $items) {
    $pagePath = Join-Path $root "data\mysqil\cassettes\$($item.id)\raw\page.html"
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
    $titleMatch = [regex]::Match($html, '(?is)<h1\b[^>]*>(.*?)</h1>')
    if (-not $titleMatch.Success) { throw "No detail title found: $($item.source_url)" }
    $item.name = ([Net.WebUtility]::HtmlDecode([regex]::Replace($titleMatch.Groups[1].Value, '(?is)<[^>]+>', ' ')) -replace '\s+', ' ').Trim()
    if (-not $item.name -or $html -notmatch [regex]::Escape($item.name)) { throw "Could not verify detail title: $($item.id)" }
    $item | Add-Member -NotePropertyName raw_page -NotePropertyValue "data/mysqil/cassettes/$($item.id)/raw/page.html"
    $item | Add-Member -NotePropertyName page_updated -NotePropertyValue $downloaded

    $imagePaths = @([regex]::Matches($html, '(?i)\bsrc="(/images/cassettes/[^"?#]+)"') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
    if ($imagePaths.Count -ne 3) { throw "Expected three quality images on $($item.source_url), found $($imagePaths.Count)." }
    $itemImages = @()
    foreach ($imagePath in $imagePaths) {
        $imageUrl = "$origin$imagePath"
        $quality = [IO.Path]::GetFileNameWithoutExtension(([Uri]$imageUrl).AbsolutePath).ToLowerInvariant()
        if ($quality -notin @('gold', 'purple', 'blue')) { throw "Unexpected cassette image tier '$quality' on $($item.id)." }
        $assetPath = "data/resources/encyclopedia/cassettes/$($item.id)/$quality.webp"
        $target = [IO.Path]::GetFullPath((Join-Path $root ($assetPath -replace '/', '\')))
        if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Asset path escaped workspace: $target" }
        $assetTasks[$imageUrl] = [pscustomobject]@{ url = $imageUrl; target = $target; local_path = $assetPath; item_id = $item.id; quality = $quality }
        $itemImages += $quality
    }
    if (@($itemImages | Select-Object -Unique).Count -ne 3) { throw "Duplicate image tier found on $($item.id)." }
    Write-Output "PAGE $($item.id) $(if ($downloaded) { 'downloaded' } else { 'cached' })"
}

$refreshAssets = [bool]$Refresh
$agent = $userAgent
$assetResults = @($assetTasks.Values | ForEach-Object -Parallel {
    $task = $_
    $temporaryPath = $task.target + ".download"
    try {
        if ((Test-Path -LiteralPath $task.target) -and -not $using:refreshAssets) {
            $bytes = [IO.File]::ReadAllBytes($task.target)
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $task.target) | Out-Null
            $response = Invoke-WebRequest -Uri $task.url -TimeoutSec 45 -UseBasicParsing -UserAgent $using:agent -OutFile $temporaryPath -PassThru
            if ($response.StatusCode -ne 200 -or $response.Headers['Content-Type'] -notmatch '^image/') { throw "Unexpected image response: $($response.StatusCode) $($response.Headers['Content-Type'])" }
            $bytes = [IO.File]::ReadAllBytes($temporaryPath)
            if ($bytes.Length -lt 16) { throw "Downloaded image is unexpectedly small ($($bytes.Length) bytes)." }
            Move-Item -LiteralPath $temporaryPath -Destination $task.target -Force
        }
        $sha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([byte[]]$bytes)).ToLowerInvariant()
        [pscustomobject]@{ item_id = $task.item_id; quality = $task.quality; source_url = $task.url; local_path = $task.local_path; sha256 = $sha; status = 'ok' }
    } catch {
        if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
        [pscustomobject]@{ item_id = $task.item_id; quality = $task.quality; source_url = $task.url; local_path = $task.local_path; status = 'failed'; error = $_.Exception.Message }
    }
} -ThrottleLimit 4)
$failedAssets = @($assetResults | Where-Object status -eq 'failed')
if ($failedAssets.Count) {
    $failedAssets | ForEach-Object { Write-Warning "ASSET $($_.source_url): $($_.error)" }
    throw "Failed to download $($failedAssets.Count) cassette images."
}

foreach ($item in $items) {
    $item | Add-Member -NotePropertyName images -NotePropertyValue @($assetResults | Where-Object item_id -eq $item.id | Sort-Object quality | ForEach-Object { $_ | Select-Object quality,source_url,local_path,sha256 })
    $item.PSObject.Properties.Remove('page_updated')
}
$manifest = [ordered]@{
    source = 'Mysqil · 环世全鉴'
    source_index = "$origin/cassettes/"
    source_license = 'CC BY-NC-SA 4.0'
    source_license_url = 'https://creativecommons.org/licenses/by-nc-sa/4.0/'
    source_author = 'Matsuzaka Yuki'
    retrieved_at = $timestamp
    expected_count = $expectedCount
    items = $items
}
$rosterPath = Join-Path $root "data\mysqil\cassettes\roster.json"
Save-Text $rosterPath (ConvertTo-Json -InputObject $manifest -Depth 12)
$pagesComplete = @($items | Where-Object { Test-Path -LiteralPath (Join-Path $root ($_.raw_page -replace '/', '\')) }).Count
$imagesComplete = @($assetResults | Where-Object { Test-Path -LiteralPath (Join-Path $root ($_.local_path -replace '/', '\')) }).Count
if ($pagesComplete -ne $expectedCount -or $imagesComplete -ne ($expectedCount * 3)) { throw "Post-download coverage mismatch: pages=$pagesComplete/$expectedCount images=$imagesComplete/$($expectedCount * 3)." }
Write-Output "SUMMARY items=$($items.Count) pages=$pagesComplete images=$imagesComplete failures=$($failedAssets.Count)"
