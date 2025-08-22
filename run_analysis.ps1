# PowerShell script to run outage data analysis in continuous monitoring loop
# Usage: .\run_analysis.ps1 -TelegramToken "1234567890ABCDEF..." -TelegramChatId "-1003012377346" -SleepMinutes 10

param(
    [string]$TelegramToken = $null,
    [string]$TelegramChatId = $null,
    [string]$TelegramThreadId = $null,
    [string]$GeocodeApiKey = $null,
    [int]$SleepMinutes = 5
)

# Configuration
$sleepSeconds = $SleepMinutes * 60

# Analysis thresholds (will be moved to arguments later)
$EXPECTED_LENGTH_THRESHOLD_HOURS = 1
$CUSTOMER_THRESHOLD = 5
$ELAPSED_TIME_THRESHOLD_HOURS = 0.25

Write-Host "Starting continuous outage monitoring..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Yellow
Write-Host "Running every $SleepMinutes minutes" -ForegroundColor Yellow
if ($TelegramToken -and $TelegramChatId) {
    Write-Host "Telegram notifications: ENABLED (Chat ID: $TelegramChatId)" -ForegroundColor Green
} else {
    Write-Host "Telegram notifications: DISABLED" -ForegroundColor Yellow
}
Write-Host ""

$iteration = 1

while ($true) {
    try {
        Write-Host "=== Monitoring Iteration $iteration - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan
        
        # Configuration for utilities
        $utilities = @(
            @{
                Name = "PSE"
                RepoPath = "..\pse-outage"
                OutputPath = "..\pse-outage\output_files"
                SourceFile = "..\pse-outage\pse-events.json"
                UtilityCode = "pse"
            },
            @{
                Name = "SCL"
                RepoPath = "..\scl-outage"
                OutputPath = "..\scl-outage\output_files"
                SourceFile = "..\scl-outage\scl-events.json"
                UtilityCode = "scl"
            },
            @{
                Name = "SNOPUD"
                RepoPath = "..\snopud-outage"
                OutputPath = "..\snopud-outage\output_files"
                SourceFile = "..\snopud-outage\KMLOutageAreas.xml"
                UtilityCode = "snopud"
            }
        )
        
        # Process each utility separately to allow conditional logic based on new data availability
        foreach ($utility in $utilities) {
            Write-Host "Processing $($utility.Name)..." -ForegroundColor Cyan
            Write-Host "  Expanding $($utility.Name) outage data..." -ForegroundColor White
            
            # Run expand.py for this utility
            py expand.py -r $utility.RepoPath -i -o $utility.OutputPath -l 10 $utility.SourceFile
            $expandResult = $LASTEXITCODE
            
            if ($expandResult -eq 0) {
                Write-Host "  $($utility.Name): New data found, proceeding with analysis..." -ForegroundColor Green
                Write-Host "  Creating $($utility.Name) dataframe..." -ForegroundColor White
                py create_outages_dataframe.py -d $utility.OutputPath -u $utility.UtilityCode --latestfiles -o "$($utility.UtilityCode)_current_outages.csv"
                
                $csvFile = "$($utility.UtilityCode)_current_outages.csv"
                if (Test-Path $csvFile) {
                    Write-Host "  Analyzing $($utility.Name) outages..." -ForegroundColor White
                    
                    # Build analyze command with optional Telegram parameters
                    $analyzeCmd = "py .\analyze_current_outages.py -u $($utility.UtilityCode) -f $csvFile -l $EXPECTED_LENGTH_THRESHOLD_HOURS -c $CUSTOMER_THRESHOLD -e $ELAPSED_TIME_THRESHOLD_HOURS"
                    if ($TelegramToken -and $TelegramChatId) {
                        $analyzeCmd += " --telegram-token `"$TelegramToken`" --telegram-chat-id `"$TelegramChatId`""
                        if ($TelegramThreadId) {
                            $analyzeCmd += " --telegram-thread-id `"$TelegramThreadId`""
                        }
                    }
                    if ($GeocodeApiKey) {
                        $analyzeCmd += " --geocode-api-key `"$GeocodeApiKey`""
                    }
                    
                    # Execute the command
                    Invoke-Expression $analyzeCmd
                }
            } elseif ($expandResult -eq 1) {
                Write-Host "  $($utility.Name): No new data, skipping analysis" -ForegroundColor Yellow
            } else {
                Write-Host "  $($utility.Name): Error during expand (exit code: $expandResult)" -ForegroundColor Red
            }
        }

        Write-Host "Iteration $iteration completed successfully" -ForegroundColor Green
        
        # Wait before next iteration
        Write-Host "Waiting $($sleepSeconds / 60) minutes before next check..." -ForegroundColor Yellow
        Start-Sleep -Seconds $sleepSeconds
        
        $iteration++
        Write-Host ""
        
    } catch {
        Write-Host "Error in iteration $iteration`: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Continuing to next iteration in $($sleepSeconds / 60) minutes..." -ForegroundColor Yellow
        Start-Sleep -Seconds $sleepSeconds
        $iteration++
    }
}

# Example with email notifications enabled:
# py .\analyze_current_outages.py -f pse_outages_dataframe.csv -l 3 -c 50 -e .5 --email admin@company.com ops@company.com
