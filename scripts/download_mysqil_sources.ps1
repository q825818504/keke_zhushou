param([switch]$Refresh)
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$origin = "https://wiki.mysqil.com"
$userAgent = "Mozilla/5.0 (compatible; KekeZhushouLocalImporter/1.0)"
$timestamp = [DateTime]::UtcNow.ToString("o")

function Get-Page([string]$Url) {
    Invoke-WebRequest -Uri $Url -TimeoutSec 45 -UseBasicParsing -UserAgent $userAgent
}

function Save-Html([string]$Url, [string]$Target, [bool]$Force) {
    if ((Test-Path -LiteralPath $Target) -and -not $Force) {
        return [pscustomobject]@{ Content = [IO.File]::ReadAllText($Target, [Text.Encoding]::UTF8); Downloaded = $false }
    }
    $response = Get-Page $Url
    if ($response.StatusCode -ne 200) { throw "HTTP $($response.StatusCode): $Url" }
    $parent = Split-Path -Parent $Target
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    [IO.File]::WriteAllText($Target, $response.Content, [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{ Content = $response.Content; Downloaded = $true }
}

$index = Get-Page "$origin/sitemap-index.xml"
$sitemapUrl = [regex]::Matches($index.Content, "(?is)<loc>(.*?)</loc>") | ForEach-Object { $_.Groups[1].Value } | Select-Object -First 1
if (-not $sitemapUrl.StartsWith($origin, [StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected sitemap URL: $sitemapUrl" }
$sitemap = Get-Page $sitemapUrl
$roster = @(
    [regex]::Matches($sitemap.Content, "(?is)<loc>(.*?)</loc>") |
        ForEach-Object {
            $url = $_.Groups[1].Value.Trim()
            $uri = [Uri]$url
            if ($uri.Host -eq ([Uri]$origin).Host -and $uri.AbsolutePath -match "^/characters/([a-z0-9-]+)/?$") {
                [pscustomobject]@{ slug = $Matches[1]; source_url = "$origin/characters/$($Matches[1])/" }
            }
        } |
        Where-Object { $_ -and $_.slug -ne "zhenhong" } |
        Sort-Object slug
)
if ($roster.Count -ne 24) { throw "Expected 24 non-Zhenhong character pages, found $($roster.Count)." }
$rosterPath = Join-Path $root "data\mysqil\characters\roster.json"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $rosterPath) | Out-Null
[IO.File]::WriteAllText($rosterPath, (ConvertTo-Json -InputObject $roster -Depth 8), [Text.UTF8Encoding]::new($false))

$pages = @()
foreach ($entry in $roster) {
    $target = Join-Path $root "data\mysqil\characters\$($entry.slug)\raw\page.html"
    $result = Save-Html $entry.source_url $target $Refresh.IsPresent
    $pages += [pscustomobject]@{ slug = $entry.slug; url = $entry.source_url; path = $target; content = $result.Content }
    Write-Output "PAGE $($entry.slug) $(if ($result.Downloaded) { 'downloaded' } else { 'cached' })"
}

$equipment = @{}
$assetTasks = @{}
foreach ($page in $pages) {
    $equipmentMatches = [regex]::Matches($page.content, '(?i)href="(/(weapons|cassettes)/([^/"?#]+)/?)(?:[?#][^"]*)?"')
    foreach ($match in $equipmentMatches) {
        $path = $match.Groups[1].Value
        $kind = $match.Groups[2].Value
        $id = [Uri]::UnescapeDataString($match.Groups[3].Value)
        $encodedId = [Uri]::EscapeDataString($id)
        $equipment["$kind/$id"] = [pscustomobject]@{ kind = $kind; id = $id; url = "$origin/$kind/$encodedId/" }
    }
    $sources = [regex]::Matches($page.content, '(?i)<img\b[^>]*\bsrc="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    foreach ($src in $sources) {
        if ($src -notmatch "^/images/") { continue }
        $uri = [Uri]("$origin$src")
        $parts = $uri.AbsolutePath -split "/"
        if ($parts.Count -lt 4) { continue }
        $category = $parts[2]
        if ($category -eq "characters") {
            $stem = [IO.Path]::GetFileNameWithoutExtension($parts[-1])
            if ($stem -notin @($page.slug, "$($page.slug)-icon")) { continue }
        } elseif ($category -notin @("weapons", "cassettes", "awaken", "ui", "items")) { continue }
        $relative = $uri.AbsolutePath.Substring("/images/".Length)
        $relativePath = "data/resources/characters/$($page.slug)/$relative"
        $target = [IO.Path]::GetFullPath((Join-Path $root ($relativePath -replace "/", "\")))
        if (-not $target.StartsWith($root + "\", [StringComparison]::OrdinalIgnoreCase)) { throw "Asset path escaped workspace: $target" }
        $assetTasks["$($page.slug)|$($uri.AbsoluteUri)"] = [pscustomobject]@{ url = $uri.AbsoluteUri; target = $target }
    }
    $upgradeMatch = [regex]::Match($page.content, '(?is)data-upgrade="([^"]+)"')
    if ($upgradeMatch.Success) {
        try {
            $upgradeText = [Net.WebUtility]::HtmlDecode($upgradeMatch.Groups[1].Value)
            $upgrade = $upgradeText | ConvertFrom-Json -Depth 100
            foreach ($material in $upgrade.materials.PSObject.Properties) {
                $filename = [IO.Path]::GetFileNameWithoutExtension([string]$material.Value.icon)
                if (-not $filename) { continue }
                $url = "$origin/images/items/$filename.webp"
                $relativePath = "data/resources/characters/$($page.slug)/items/$filename.webp"
                $target = Join-Path $root ($relativePath -replace "/", "\")
                $assetTasks["$($page.slug)|$url"] = [pscustomobject]@{ url = $url; target = $target }
            }
        } catch {
            Write-Warning "Could not read material icons for $($page.slug): $($_.Exception.Message)"
        }
    }
}

foreach ($item in $equipment.Values | Sort-Object kind,id) {
    $target = Join-Path $root "data\mysqil\$($item.kind)\$($item.id)\raw\page.html"
    $result = Save-Html $item.url $target $Refresh.IsPresent
    Write-Output "ITEM $($item.kind)/$($item.id) $(if ($result.Downloaded) { 'downloaded' } else { 'cached' })"
}

$refreshAssets = $Refresh.IsPresent
$assetResults = @(
    $assetTasks.Values | ForEach-Object -Parallel {
        $task = $_
        try {
            if ((Test-Path -LiteralPath $task.target) -and -not $using:refreshAssets) {
                return [pscustomobject]@{ status = "cached"; target = $task.target; url = $task.url }
            }
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $task.target) | Out-Null
            Invoke-WebRequest -Uri $task.url -TimeoutSec 45 -UseBasicParsing -UserAgent $using:userAgent -OutFile $task.target
            [pscustomobject]@{ status = "downloaded"; target = $task.target; url = $task.url }
        } catch {
            [pscustomobject]@{ status = "failed"; target = $task.target; url = $task.url; error = $_.Exception.Message }
        }
    } -ThrottleLimit 6
)
$failedAssets = @($assetResults | Where-Object status -eq "failed")
foreach ($failure in $failedAssets) { Write-Warning "ASSET failed: $($failure.url) — $($failure.error)" }
Write-Output "SUMMARY character_pages=$($pages.Count) equipment_pages=$($equipment.Count) assets=$($assetTasks.Count) asset_failures=$($failedAssets.Count)"
