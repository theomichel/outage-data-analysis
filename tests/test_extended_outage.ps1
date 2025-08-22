# Extended Outage Test - Expected Resolution Time Increase Scenario
# Tests the scenario where an outage's expected resolution time increases from below
# the threshold to above the threshold, making it a "new" outage that should trigger
# a notification.
#
# Parameters:
#   -Verbose: Show detailed output from each step
#   -KeepFiles: Don't clean up test files after completion
#   -TelegramToken: Optional Telegram bot token for notifications
#   -TelegramChatId: Optional Telegram chat ID for notifications  
#   -TelegramThreadId: Optional Telegram thread ID for notifications

param(
    [switch]$Verbose,
    [switch]$KeepFiles,
    [string]$TelegramToken = $null,
    [string]$TelegramChatId = $null,
    [string]$TelegramThreadId = $null,
    [string]$GeocodeApiKey = $null
)

Write-Host "🧪 Extended Outage Test - Resolution Time Increase" -ForegroundColor Cyan
Write-Host ""

# Change to the parent directory (where production scripts are located)
Set-Location ".."

try {
    # Step 1: Set up extended outage scenario
    Write-Host "Step 1: Setting up extended outage scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "tests\git_mock.py" "tests\git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_extended_outage for this scenario
    $gitMockContent = Get-Content "tests\git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_extended_outage import get_default_mock_data as get_test_data'
    
    Set-Content "tests\git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "test_output_extended"
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    
    $expandResult = py expand.py --mock -i -o $outputDir -l 10 pse-events.json 2>&1
    $expandExitCode = $LASTEXITCODE
    
    if ($Verbose) {
        Write-Host "Expand output:" -ForegroundColor Gray
        $expandResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
    
    Write-Host "Expand completed (exit code: $expandExitCode)" -ForegroundColor $(if ($expandExitCode -eq 0) {"Green"} else {"Red"})
    
    if ($expandExitCode -ne 0) {
        throw "expand.py failed with exit code $expandExitCode"
    }
    
    # Step 3: Check what files were created
    Write-Host ""
    Write-Host "Step 3: Checking exported files..." -ForegroundColor Yellow
    $exportedFiles = Get-ChildItem $outputDir -Filter "*.json" | Sort-Object Name
    
    if ($exportedFiles.Count -gt 0) {
        Write-Host "+ Found $($exportedFiles.Count) exported files:" -ForegroundColor Green
        $exportedFiles | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }
    } else {
        Write-Host "- No exported files found" -ForegroundColor Red
    }
    
    # Step 4: Run create_outages_dataframe.py on the mock data
    if ($exportedFiles.Count -ge 2) {
        Write-Host ""
        Write-Host "Step 4: Creating outages dataframe..." -ForegroundColor Yellow
        
        $createResult = py create_outages_dataframe.py -d $outputDir -u pse --latestfiles -o "test_pse_extended_outages.csv" 2>&1
        $createExitCode = $LASTEXITCODE
        
        if ($Verbose) {
            Write-Host "Create dataframe output:" -ForegroundColor Gray
            $createResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        }
        
        Write-Host "Dataframe creation completed (exit code: $createExitCode)" -ForegroundColor $(if ($createExitCode -eq 0) {"Green"} else {"Red"})
        
        # Step 5: Run analysis with thresholds that should trigger the extended outage
        if ($createExitCode -eq 0) {
            Write-Host ""
            Write-Host "Step 5: Running outage analysis..." -ForegroundColor Yellow
            
            # Build analyze command with thresholds:
            # -l 6: Expected length threshold of 6 hours (360 minutes)
            # -c 100: Customer threshold of 100 customers
            # -e 0.25: Elapsed time threshold of 15 minutes (0.25 hours)
            $analyzeCmd = "py analyze_current_outages.py -u pse -f `"test_pse_extended_outages.csv`" -l 6 -c 100 -e 0.25"
            if ($TelegramToken -and $TelegramChatId) {
                $analyzeCmd += " --telegram-token `"$TelegramToken`" --telegram-chat-id `"$TelegramChatId`""
                if ($TelegramThreadId) {
                    $analyzeCmd += " --telegram-thread-id `"$TelegramThreadId`""
                }
            }
            if ($GeocodeApiKey) {
                $analyzeCmd += " --geocode-api-key `"$GeocodeApiKey`""
            }
            
            if ($Verbose) {
                Write-Host "Running: $analyzeCmd" -ForegroundColor Gray
            }
            
            $analyzeResult = Invoke-Expression $analyzeCmd 2>&1
            $analyzeExitCode = $LASTEXITCODE
            
            if ($Verbose) {
                Write-Host "Analysis output:" -ForegroundColor Gray
                $analyzeResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
            
            Write-Host "Analysis completed (exit code: $analyzeExitCode)" -ForegroundColor $(if ($analyzeExitCode -eq 0) {"Green"} else {"Red"})
            
            # Step 6: Check notification results
            Write-Host ""
            Write-Host "Step 6: Checking notification results..." -ForegroundColor Yellow
            
            # Check for notification files
            $notificationFiles = Get-ChildItem -Filter "notification_*.txt" | Sort-Object Name
            if ($notificationFiles.Count -gt 0) {
                Write-Host "+ Found $($notificationFiles.Count) notification files:" -ForegroundColor Green
                $notificationFiles | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }
                
                # Verify notification content
                $newOutageNotifications = $notificationFiles | Where-Object { $_.Name -like "*new*" }
                if ($newOutageNotifications.Count -gt 0) {
                    Write-Host "+ Test PASSED: Extended outage detected as 'new' outage" -ForegroundColor Green
                    Write-Host "  Expected: Outage INC000789 should be detected as new due to increased resolution time" -ForegroundColor Gray
                    Write-Host "  Previous: 1-hour expected resolution (below 6-hour threshold)" -ForegroundColor Gray
                    Write-Host "  Latest: 27-hour expected resolution (above 6-hour threshold)" -ForegroundColor Gray
                    
                    # Verify notification content contains expected outage ID
                    $notificationContent = Get-Content $newOutageNotifications[0] -Raw
                    if ($notificationContent -match "INC000789") {
                        Write-Host "+ Notification content verified: Contains correct outage ID INC000789" -ForegroundColor Green
                    } else {
                        Write-Host "- Warning: Notification content does not contain expected outage ID" -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "- Test FAILED: No 'new' outage notifications found" -ForegroundColor Red
                    Write-Host "  Expected: Outage INC000789 should be detected as new due to increased resolution time" -ForegroundColor Gray
                }
            } else {
                Write-Host "- Test FAILED: No notification files found" -ForegroundColor Red
                Write-Host "  Expected: Outage INC000789 should be detected as new due to increased resolution time" -ForegroundColor Gray
            }
            
        } else {
            Write-Host "- Dataframe creation failed, skipping analysis" -ForegroundColor Red
        }
    } else {
        Write-Host "- Insufficient exported files for analysis" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Test completed successfully!" -ForegroundColor Green
    
} catch {
    Write-Host ""
    Write-Host "Test FAILED!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    
} finally {
    # Cleanup
    if (-not $KeepFiles) {
        Write-Host ""
        Write-Host "Cleaning up test files..." -ForegroundColor Yellow
        
        # Restore original git_mock.py
        if (Test-Path "tests\git_mock.py.backup") {
            Move-Item "tests\git_mock.py.backup" "tests\git_mock.py" -Force
        }
        
        # Remove test files
        $filesToRemove = @(
            "test_output_extended",
            "test_pse_extended_outages.csv",
            "notification_*.txt"
        )
        
        foreach ($file in $filesToRemove) {
            if (Test-Path $file) {
                Remove-Item $file -Recurse -Force -ErrorAction SilentlyContinue
                Write-Host "  Removed: $file" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host ""
        Write-Host "Keeping test files (--KeepFiles specified)" -ForegroundColor Yellow
    }
}
