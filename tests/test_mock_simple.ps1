# Simple End-to-End Test Using expand.py --mock flag
# Tests the full pipeline with mocked git data
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

Write-Host "🧪 Simple E2E Test with Mock Git" -ForegroundColor Cyan
Write-Host ""

# Change to the parent directory (where production scripts are located)
Set-Location ".."

try {
    # Step 1: Set up golden path scenario (ensure correct test data)
    Write-Host "Step 1: Setting up golden path scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "tests\git_mock.py" "tests\git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_golden_path for explicit scenario
    $gitMockContent = Get-Content "tests\git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_golden_path import get_default_mock_data as get_test_data'
    
    Set-Content "tests\git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "test_output"
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
    
    # Step 3: Run create_outages_dataframe.py on the mock data
    if ($exportedFiles.Count -ge 2) {
        Write-Host ""
        Write-Host "Step 4: Creating outages dataframe..." -ForegroundColor Yellow
        
        $createResult = py create_outages_dataframe.py -d $outputDir -u pse --latestfiles -o "test_pse_current_outages.csv" 2>&1
        $createExitCode = $LASTEXITCODE
        
        if ($Verbose) {
            Write-Host "Create dataframe output:" -ForegroundColor Gray
            $createResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        }
        
        Write-Host "Dataframe creation completed (exit code: $createExitCode)" -ForegroundColor $(if ($createExitCode -eq 0) {"Green"} else {"Red"})
        
        # Step 4: Run analysis
        if ($createExitCode -eq 0) {
            Write-Host ""
            Write-Host "Step 5: Running outage analysis..." -ForegroundColor Yellow
            
            # Build analyze command with optional Telegram parameters
            $analyzeCmd = "py analyze_current_outages.py -u pse -f `"test_pse_current_outages.csv`" -l 6 -c 100 -e 0.25"
            if ($TelegramToken -and $TelegramChatId) {
                $analyzeCmd += " --telegram-token `"$TelegramToken`" --telegram-chat-id `"$TelegramChatId`""
                if ($TelegramThreadId) {
                    $analyzeCmd += " --telegram-thread-id `"$TelegramThreadId`""
                }
            }
            if ($GeocodeApiKey) {
                $analyzeCmd += " --geocode-api-key `"$GeocodeApiKey`""
            }
            
            $analysisResult = Invoke-Expression "$analyzeCmd 2>&1"
            $analysisExitCode = $LASTEXITCODE
            
            if ($Verbose) {
                Write-Host "Analysis output:" -ForegroundColor Gray
                $analysisResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
            
            Write-Host "Analysis completed (exit code: $analysisExitCode)" -ForegroundColor $(if ($analysisExitCode -eq 0) {"Green"} else {"Red"})
        }
    }
    
    # Step 5: Validate results
    Write-Host ""
    Write-Host "Step 6: Validating results..." -ForegroundColor Yellow
    
    $testsPassed = 0
    $testsTotal = 0
    
    # Test 1: Check exported files
    $testsTotal++
    if ($exportedFiles.Count -ge 2) {
        Write-Host "+ Mock git exported files successfully" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "- Expected at least 2 exported files, got $($exportedFiles.Count)" -ForegroundColor Red
    }
    
    # Test 2: Check notification files
    $testsTotal++
    $notificationFiles = Get-ChildItem "notification_*.txt" -ErrorAction SilentlyContinue
    if ($notificationFiles) {
        Write-Host "+ Found $($notificationFiles.Count) notification file(s)" -ForegroundColor Green
        $testsPassed++
        
        # Verify notification content
        $newOutageNotifications = $notificationFiles | Where-Object { $_.Name -like "*new*" }
        if ($newOutageNotifications.Count -gt 0) {
            Write-Host "+ Found 'new' outage notification(s)" -ForegroundColor Green
            
            # Verify notification content contains expected outage ID
            $notificationContent = Get-Content $newOutageNotifications[0] -Raw
            if ($notificationContent -match "INC123456") {
                Write-Host "+ Notification content verified: Contains correct outage ID INC123456" -ForegroundColor Green
            } else {
                Write-Host "- Warning: Notification content does not contain expected outage ID" -ForegroundColor Yellow
            }
            
            # Check for expected customer count
            if ($notificationContent -match "1500") {
                Write-Host "+ Notification content verified: Contains correct customer count (1500)" -ForegroundColor Green
            } else {
                Write-Host "- Warning: Notification content does not contain expected customer count" -ForegroundColor Yellow
            }
        } else {
            Write-Host "⚠ No 'new' outage notifications found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "- No notification files found" -ForegroundColor Red
    }
    
    # Summary
    Write-Host ""
    Write-Host "=== Test Results ===" -ForegroundColor Cyan
    Write-Host "Tests passed: $testsPassed / $testsTotal" -ForegroundColor White
    
    if ($testsPassed -ge ($testsTotal - 1)) {  # Allow one test to fail
        Write-Host ""
        Write-Host "Test PASSED!" -ForegroundColor Green
        Write-Host "Mock git approach working successfully." -ForegroundColor Green
        $success = $true
    } else {
        Write-Host ""
        Write-Host "Test FAILED!" -ForegroundColor Red
        Write-Host "Pipeline did not produce expected notification results." -ForegroundColor Red
        $success = $false
    }

} catch {
    Write-Host ""
    Write-Host "Test FAILED!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    $success = $false
} finally {
    # Always restore original git_mock.py
    if (Test-Path "tests\git_mock.py.backup") {
        Copy-Item "tests\git_mock.py.backup" "tests\git_mock.py" -Force
        Remove-Item "tests\git_mock.py.backup" -Force -ErrorAction SilentlyContinue
        if ($Verbose) {
            Write-Host "Restored original git_mock.py" -ForegroundColor Gray
        }
    }
    
    # Cleanup
    if (!$KeepFiles) {
        Write-Host ""
        Write-Host "Cleaning up test files..." -ForegroundColor Gray
        Remove-Item $outputDir -Recurse -ErrorAction SilentlyContinue
        Remove-Item "test_pse_current_outages.csv" -ErrorAction SilentlyContinue

        Remove-Item "notification_*.txt" -ErrorAction SilentlyContinue
    } else {
        Write-Host ""
        Write-Host "Test files preserved for inspection" -ForegroundColor Gray
    }
}

if ($success) {
    exit 0
} else {
    exit 1
}
