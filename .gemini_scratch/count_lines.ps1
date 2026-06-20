$excludeDirs = @('node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build', '.pytest_cache', '.mypy_cache', '.gemini_scratch', 'package-lock.json')

$files = Get-ChildItem -Path "c:\Users\ASUS\Desktop\cv-analyzer" -Recurse -File | Where-Object {
    $path = $_.FullName
    $exclude = $false
    foreach ($dir in $excludeDirs) {
        if ($path -match [regex]::Escape("\$dir\")) {
            $exclude = $true
            break
        }
    }
    -not $exclude
}

$results = @{}

foreach ($f in $files) {
    $ext = $f.Extension
    if (-not $ext) { $ext = $f.Name }
    if (-not $results.ContainsKey($ext)) {
        $results[$ext] = @{FileCount=0; Lines=0; Bytes=0}
    }
    $results[$ext].FileCount++
    $results[$ext].Bytes += $f.Length
    try {
        $lineCount = (Get-Content $f.FullName -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        $results[$ext].Lines += $lineCount
    } catch {}
}

Write-Host "`nExtension | Files | Lines | Size (KB)"
Write-Host "----------|-------|-------|----------"
$results.GetEnumerator() | Sort-Object { $_.Value.Lines } -Descending | ForEach-Object {
    $sizeKB = [math]::Round($_.Value.Bytes / 1024, 1)
    Write-Host ("{0} | {1} | {2} | {3}" -f $_.Key, $_.Value.FileCount, $_.Value.Lines, $sizeKB)
}

$totalFiles = ($results.Values | Measure-Object -Property FileCount -Sum).Sum
$totalLines = ($results.Values | Measure-Object -Property Lines -Sum).Sum
$totalBytes = ($results.Values | Measure-Object -Property Bytes -Sum).Sum
$totalKB = [math]::Round($totalBytes / 1024, 1)
Write-Host "`nTOTAL | $totalFiles | $totalLines | $totalKB"
