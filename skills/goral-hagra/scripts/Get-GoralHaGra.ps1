<#
.SYNOPSIS
    Interacts with the Sefaria REST API to support the Goral HaGra skill.
.DESCRIPTION
    Provides actions for random verse selection, translation lookup, verse data retrieval,
    and related text search using the Sefaria API.
#>
param(
    [ValidateSet('random-verse', 'get-translations', 'get-verse-data', 'search-related')]
    [string]$Action = 'random-verse',

    [ValidateSet('torah', 'tanakh')]
    [string]$Mode = 'torah',

    [string]$Reference,
    [string]$Translation,
    [string]$Query,
    [string[]]$Filters,
    [int]$Size = 5
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-SefariaEncodedRef {
    param([string]$Ref)
    $Ref -replace ' ', '%20'
}

function Strip-HtmlTags {
    param([string]$Html)
    if (-not $Html) { return '' }
    # Remove HTML tags, decode common entities
    $text = $Html -replace '<[^>]+>', ''
    $text = $text -replace '&amp;', '&'
    $text = $text -replace '&lt;', '<'
    $text = $text -replace '&gt;', '>'
    $text = $text -replace '&quot;', '"'
    $text = $text -replace '&#39;', "'"
    $text = $text -replace '&nbsp;', ' '
    $text = $text -replace '\s+', ' '
    $text.Trim()
}

function Invoke-SefariaApi {
    param(
        [string]$Uri,
        [string]$Method = 'GET',
        [object]$Body
    )
    $params = @{
        Uri         = $Uri
        Method      = $Method
        ContentType = 'application/json; charset=utf-8'
    }
    if ($Body) {
        $params.Body = $Body | ConvertTo-Json -Depth 10
    }
    Invoke-RestMethod @params
}

switch ($Action) {
    'random-verse' {
        try {
            $dataPath = Join-Path $PSScriptRoot '..\data\tanakh-verses.json'
            $data = Get-Content -Path $dataPath -Raw -Encoding UTF8 | ConvertFrom-Json

            if ($Mode -eq 'torah') {
                $books = [array]$data.torah
            } else {
                $books = [System.Collections.ArrayList]::new()
                $books.AddRange([array]$data.torah)
                $books.AddRange([array]$data.neviim)
                $books.AddRange([array]$data.ketuvim)
            }
            $totalVerses = [int]($books | Measure-Object -Property totalVerses -Sum).Sum

            $randomNum = Get-Random -Minimum 0 -Maximum $totalVerses

            $selectedBook = $null
            foreach ($book in $books) {
                if ($randomNum -lt ($book.cumulativeOffset + $book.totalVerses)) {
                    $selectedBook = $book
                    break
                }
            }

            $verseIndex = $randomNum - $selectedBook.cumulativeOffset
            $cumulative = 0
            $chapter = 0
            $verse = 0
            $versesPerChapter = @($selectedBook.verses)
            for ($i = 0; $i -lt $versesPerChapter.Count; $i++) {
                $chapterVerses = $versesPerChapter[$i]
                if ($verseIndex -lt ($cumulative + $chapterVerses)) {
                    $chapter = $i + 1
                    $verse = $verseIndex - $cumulative + 1
                    break
                }
                $cumulative += $chapterVerses
            }

            @{
                reference  = "$($selectedBook.name) ${chapter}:${verse}"
                hebrewName = $selectedBook.hebrewName
                book       = $selectedBook.name
                chapter    = $chapter
                verse      = $verse
                mode       = $Mode
            } | ConvertTo-Json -Depth 10
        }
        catch {
            @{ error = "Failed to select random verse: $($_.Exception.Message)" } | ConvertTo-Json -Depth 10
        }
    }

    'get-translations' {
        if (-not $Reference) {
            @{ error = "Parameter -Reference is required for get-translations" } | ConvertTo-Json -Depth 10
            return
        }
        try {
            $encodedRef = Get-SefariaEncodedRef $Reference
            $uri = "https://www.sefaria.org/api/v3/texts/${encodedRef}?version=english|all"
            $response = Invoke-SefariaApi -Uri $uri

            $translations = @()
            foreach ($ver in $response.versions) {
                if ($ver.versionTitle) {
                    $translations += $ver.versionTitle
                }
            }

            @{
                reference    = $Reference
                translations = $translations
            } | ConvertTo-Json -Depth 10
        }
        catch {
            @{ error = "Failed to fetch translations for '${Reference}': $($_.Exception.Message)" } | ConvertTo-Json -Depth 10
        }
    }

    'get-verse-data' {
        if (-not $Reference) {
            @{ error = "Parameter -Reference is required for get-verse-data" } | ConvertTo-Json -Depth 10
            return
        }
        try {
            $encodedRef = Get-SefariaEncodedRef $Reference

            # Build text API URL
            if ($Translation) {
                $encodedTranslation = [System.Net.WebUtility]::UrlEncode($Translation)
                $textUri = "https://www.sefaria.org/api/v3/texts/${encodedRef}?version=english|${encodedTranslation}&version=source"
            } else {
                $textUri = "https://www.sefaria.org/api/v3/texts/${encodedRef}?version=source&version=english"
            }

            $textResponse = Invoke-SefariaApi -Uri $textUri

            $hebrewText = ''
            $englishText = ''
            $englishVersionTitle = ''
            foreach ($ver in $textResponse.versions) {
                if ($ver.languageFamilyName -eq 'Hebrew') {
                    $hebrewText = $ver.text
                }
                if ($ver.languageFamilyName -eq 'English') {
                    $englishText = $ver.text
                    $englishVersionTitle = $ver.versionTitle
                }
            }

            # Fetch commentary/links
            $linksUri = "https://www.sefaria.org/api/links/${encodedRef}?with_text=1"
            $linksResponse = Invoke-SefariaApi -Uri $linksUri

            $relevantCategories = @('Commentary', 'Targum', 'Midrash', 'Talmud')
            $seen = @{}
            $commentary = @()
            foreach ($link in $linksResponse) {
                if ($link.category -and $relevantCategories -contains $link.category) {
                    $commentator = if ($link.collectiveTitle.en) { $link.collectiveTitle.en } else { $link.sourceRef -replace ' on .*', '' }
                    # Skip if we already have this commentator or text is empty/array
                    if ($seen.ContainsKey($commentator)) { continue }
                    $rawText = $link.text
                    if ($rawText -is [System.Array] -or -not $rawText) { continue }
                    $cleanText = Strip-HtmlTags $rawText
                    if (-not $cleanText) { continue }
                    $seen[$commentator] = $true
                    $commentary += @{
                        commentator = $commentator
                        text        = $cleanText
                    }
                    if ($commentary.Count -ge 6) { break }
                }
            }

            @{
                reference           = $Reference
                hebrew              = $hebrewText
                english             = $englishText
                englishVersionTitle = $englishVersionTitle
                commentary          = $commentary
            } | ConvertTo-Json -Depth 10
        }
        catch {
            @{ error = "Failed to fetch verse data for '${Reference}': $($_.Exception.Message)" } | ConvertTo-Json -Depth 10
        }
    }

    'search-related' {
        if (-not $Query) {
            @{ error = "Parameter -Query is required for search-related" } | ConvertTo-Json -Depth 10
            return
        }
        try {
            $filterFields = @()
            $searchFilters = @()
            if ($Filters) {
                $searchFilters = $Filters
                $filterFields = $Filters | ForEach-Object { $null }
            }

            $body = @{
                query              = $Query
                filters            = $searchFilters
                filter_fields      = $filterFields
                size               = $Size
                field              = 'naive_lemmatizer'
                sort_method        = 'score'
                sort_reverse       = $false
                sort_score_missing = 0.04
                source_proj        = $true
                type               = 'text'
                aggs               = @()
                slop               = 10
                sort_fields        = @('pagesheetrank')
            }

            $uri = 'https://www.sefaria.org/api/search-wrapper/es8'
            $response = Invoke-SefariaApi -Uri $uri -Method 'POST' -Body $body

            $results = @()
            foreach ($hit in $response.hits.hits) {
                $results += @{
                    ref        = $hit._source.ref
                    heRef      = $hit._source.heRef
                    categories = $hit._source.categories
                    text       = $hit._source.exact
                    highlights = $hit.highlight.naive_lemmatizer
                }
            }

            @{
                query   = $Query
                results = $results
            } | ConvertTo-Json -Depth 10
        }
        catch {
            @{ error = "Failed to search for '${Query}': $($_.Exception.Message)" } | ConvertTo-Json -Depth 10
        }
    }
}
