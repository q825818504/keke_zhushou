param([switch]$Refresh)
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$origin = "https://wiki.mysqil.com"
$userAgent = "Mozilla/5.0 (compatible; KekeZhushouLocalImporter/1.0)"
$timestamp = [DateTime]::UtcNow.ToString("o")
$qualityNames = @{ Orange = 'gold'; Purple = 'purple'; Blue = 'blue' }

function Get-Page([string]$Url) {
    Invoke-WebRequest -Uri $Url -TimeoutSec 45 -UseBasicParsing -UserAgent $userAgent
}

function Save-Text([string]$Path, [string]$Text) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Get-LocalPath([string]$UrlPath) {
    $segments = $UrlPath.TrimStart('/').Split('/')
    if ($segments.Count -lt 2 -or $segments -contains '..' -or ($segments | Where-Object { $_ -notmatch '^[\p{L}\p{N}_.-]+$' })) {
        throw "Unsafe source asset path: $UrlPath"
    }
    $relative = "data/resources/encyclopedia/driver_blocks/site/$($segments -join '/')"
    $target = [IO.Path]::GetFullPath((Join-Path $root ($relative -replace '/', '\')))
    if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Asset path escaped workspace: $target" }
    [pscustomobject]@{ local_path = $relative; target = $target }
}

$indexUrl = "$origin/drivers"
$indexResponse = Get-Page $indexUrl
if ($indexResponse.StatusCode -ne 200) { throw "Unexpected driver-block index status: $($indexResponse.StatusCode)" }
$indexHtml = $indexResponse.Content
$indexPath = Join-Path $root "data\mysqil\driver-blocks\raw\index.html"
Save-Text $indexPath $indexHtml

$shapeCountMatch = [regex]::Match($indexHtml, '共\s*(\d+)\s*种形状')
if (-not $shapeCountMatch.Success) { throw "Could not read shape count from the source driver-block index." }
$expectedShapeCount = [int]$shapeCountMatch.Groups[1].Value
$modelCounts = [ordered]@{}
foreach ($match in [regex]::Matches($indexHtml, '(Ⅱ|Ⅲ|Ⅳ)型\s*(\d+)')) {
    $modelCounts[$match.Groups[1].Value] = [int]$match.Groups[2].Value
}
if (($modelCounts.Values | Measure-Object -Sum).Sum -ne $expectedShapeCount) { throw "Declared driver-block model counts do not sum to $expectedShapeCount shapes." }

$items = [Collections.Generic.List[object]]::new()
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($match in [regex]::Matches($indexHtml, '(?is)<a\b[^>]*href="(?<href>/drivers/[^"?#]+)"[^>]*>.*?</a>')) {
    $href = [Net.WebUtility]::HtmlDecode($match.Groups['href'].Value)
    $routeMatch = [regex]::Match($href, '^/drivers/(?<slug>cell[234]_style\d+_\d+_(?<quality>Orange|Purple|Blue))$')
    if (-not $routeMatch.Success) { continue }
    $slug = $routeMatch.Groups['slug'].Value
    if (-not $seen.Add($slug)) { continue }
    $qualityName = $qualityNames[$routeMatch.Groups['quality'].Value]
    $shapeId = [regex]::Replace($slug, '_(Orange|Purple|Blue)$', '').ToLowerInvariant()
    $anchorBody = [regex]::Match($match.Value, '(?is)^<a\b[^>]*>(?<body>.*?)</a>').Groups['body'].Value
    $indexLabel = ([Net.WebUtility]::HtmlDecode([regex]::Replace($anchorBody, '(?is)<[^>]+>', ' ')) -replace '\s+', ' ').Trim()
    $items.Add([pscustomobject]@{
        id = $slug.ToLowerInvariant()
        shape_id = $shapeId
        quality = $qualityName
        source_url = "$origin$href"
        name = ''
        index_label = $indexLabel
        raw_page = "data/mysqil/driver-blocks/$($slug.ToLowerInvariant())/raw/page.html"
        image_urls = @()
    })
}
$groups = @($items | Group-Object shape_id)
$expectedPageCount = $expectedShapeCount * 3
if ($items.Count -ne $expectedPageCount -or $groups.Count -ne $expectedShapeCount) {
    throw "Index coverage mismatch: declared $expectedShapeCount shapes / $expectedPageCount quality pages, found $($groups.Count) shapes / $($items.Count) pages."
}
foreach ($group in $groups) {
    if (@($group.Group.quality | Sort-Object -Unique).Count -ne 3) { throw "Shape '$($group.Name)' does not expose all three quality pages." }
}

$guideUrl = "$origin/cassettes/drivers"
$guideRelativePath = 'data/mysqil/driver-blocks/raw/mechanism-guide.html'
$guidePath = Join-Path $root ($guideRelativePath -replace '/', '\')
$guideStatus = 'unavailable'
$guideImageUrls = @()
$guideError = ''
try {
    if ((Test-Path -LiteralPath $guidePath) -and -not $Refresh) {
        $guideHtml = [IO.File]::ReadAllText($guidePath, [Text.Encoding]::UTF8)
    } else {
        $guideResponse = Get-Page $guideUrl
        if ($guideResponse.StatusCode -ne 200) { throw "HTTP $($guideResponse.StatusCode): $guideUrl" }
        $guideHtml = $guideResponse.Content
        Save-Text $guidePath $guideHtml
    }
    if ($guideHtml -notmatch '(?is)<h1\b[^>]*>\s*驱动块\s*</h1>' -or $guideHtml -notmatch 'CC BY-NC-SA 4\.0') { throw "Mechanism guide title or source-license footer did not match." }
    $guideImageUrls = @([regex]::Matches($guideHtml, '(?i)(?:src|data-src)="(?<path>/images/(?:drivers|ui)/[^"?#]+)"') | ForEach-Object { "$origin$($_.Groups['path'].Value)" } | Select-Object -Unique)
    $guideStatus = 'saved'
} catch {
    $guideError = $_.Exception.Message
    Write-Warning "MECHANISM GUIDE $($guideUrl): $guideError"
}

$assetUrls = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$indexImageUrls = @([regex]::Matches($indexHtml, '(?i)(?:src|data-src)="(?<path>/images/(?:drivers|ui)/[^"?#]+)"') | ForEach-Object { "$origin$($_.Groups['path'].Value)" } | Select-Object -Unique)
foreach ($url in $indexImageUrls) { [void]$assetUrls.Add($url) }
foreach ($url in $guideImageUrls) { [void]$assetUrls.Add($url) }

foreach ($item in $items) {
    $pagePath = Join-Path $root ($item.raw_page -replace '/', '\')
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
    if (-not $item.name) { throw "Could not verify detail title: $($item.id)" }
    if ($html -notmatch 'CC BY-NC-SA 4\.0') { throw "Source license footer missing from $($item.source_url)" }
    $pageImages = @([regex]::Matches($html, '(?i)(?:src|data-src)="(?<path>/images/(?:drivers|ui)/[^"?#]+)"') | ForEach-Object { "$origin$($_.Groups['path'].Value)" } | Select-Object -Unique)
    if (-not ($pageImages | Where-Object { ([Uri]$_).AbsolutePath.StartsWith('/images/drivers/', [StringComparison]::OrdinalIgnoreCase) })) {
        throw "No driver-block image found in $($item.source_url)."
    }
    $item.image_urls = $pageImages
    foreach ($url in $pageImages) { [void]$assetUrls.Add($url) }
    Write-Output "PAGE $($item.id) $(if ($downloaded) { 'downloaded' } else { 'cached' }) assets=$($pageImages.Count)"
}

$assetTasks = foreach ($url in $assetUrls) {
    $urlPath = ([Uri]$url).AbsolutePath
    $path = Get-LocalPath $urlPath
    [pscustomobject]@{ url = $url; target = $path.target; local_path = $path.local_path }
}
$refreshAssets = [bool]$Refresh
$agent = $userAgent
$assetResults = @($assetTasks | ForEach-Object -Parallel {
    $task = $_
    $temporaryPath = $task.target + '.download'
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
        [pscustomobject]@{ source_url = $task.url; local_path = $task.local_path; sha256 = $sha; status = 'ok' }
    } catch {
        if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
        [pscustomobject]@{ source_url = $task.url; local_path = $task.local_path; status = 'failed'; error = $_.Exception.Message }
    }
} -ThrottleLimit 4)
$failedAssets = @($assetResults | Where-Object status -eq 'failed')
if ($failedAssets.Count) {
    $failedAssets | ForEach-Object { Write-Warning "ASSET $($_.source_url): $($_.error)" }
    throw "Failed to download $($failedAssets.Count) driver-block source assets."
}

$assetByUrl = @{}
foreach ($asset in $assetResults) { $assetByUrl[$asset.source_url] = $asset | Select-Object source_url,local_path,sha256 }
foreach ($item in $items) { $item | Add-Member -NotePropertyName images -NotePropertyValue @($item.image_urls | ForEach-Object { $assetByUrl[$_] }) -Force; $item.PSObject.Properties.Remove('image_urls') }
$manifest = [ordered]@{
    source = 'Mysqil · 环世全鉴'
    source_index = $indexUrl
    source_license = 'CC BY-NC-SA 4.0'
    source_license_url = 'https://creativecommons.org/licenses/by-nc-sa/4.0/'
    source_author = 'Matsuzaka Yuki'
    retrieved_at = $timestamp
    mechanism_guide = [ordered]@{
        source_url = $guideUrl
        status = $guideStatus
        raw_page = if ($guideStatus -eq 'saved') { $guideRelativePath } else { $null }
        error = $guideError
    }
    expected_shape_count = $expectedShapeCount
    expected_page_count = $expectedPageCount
    model_counts = $modelCounts
    index_raw_page = 'data/mysqil/driver-blocks/raw/index.html'
    index_images = @($indexImageUrls | ForEach-Object { $assetByUrl[$_] })
    assets = $assetResults | ForEach-Object { $_ | Select-Object source_url,local_path,sha256 }
    items = $items
}
$rosterPath = Join-Path $root 'data\mysqil\driver-blocks\roster.json'
Save-Text $rosterPath (ConvertTo-Json -InputObject $manifest -Depth 16)
$pagesComplete = @($items | Where-Object { Test-Path -LiteralPath (Join-Path $root ($_.raw_page -replace '/', '\')) }).Count
$imageCount = @($assetResults | Where-Object { Test-Path -LiteralPath (Join-Path $root ($_.local_path -replace '/', '\')) }).Count
if ($pagesComplete -ne $expectedPageCount -or $imageCount -ne $assetResults.Count) { throw "Post-download coverage mismatch: pages=$pagesComplete/$expectedPageCount assets=$imageCount/$($assetResults.Count)." }
Write-Output "SUMMARY shapes=$($groups.Count) pages=$pagesComplete assets=$imageCount failures=$($failedAssets.Count)"
