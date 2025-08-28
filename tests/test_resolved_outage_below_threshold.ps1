# Test for Resolved Outage Golden Path Scenario
# Tests the full pipeline with a large outage that gets resolved
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

Write-Host "🧪 Resolved Outage E2E Test with Mock Git" -ForegroundColor Cyan
Write-Host ""

try {
    # Step 1: Set up resolved outage scenario by modifying git_mock import
    Write-Host "Step 1: Setting up resolved outage scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "git_mock.py" "git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_resolved_below_threshold instead of test_data
    $gitMockContent = Get-Content "git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_resolved_below_threshold import get_default_mock_data as get_test_data'
    
    Set-Content "git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "output\test_resolved_output"
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    
    $expandResult = py "..\expand.py" --mock -i -o $outputDir -l 10 ..\pse-events.json 2>&1
    $expandExitCode = $LASTEXITCODE
    
    if ($Verbose) {
        Write-Host "Expand output:" -ForegroundColor Gray
        $expandResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
    
    Write-Host "Expand completed (exit code: $expandExitCode)"
    
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
        throw "No exported files found in $outputDir"
    }
    
    # Step 4: Create outages dataframe
    Write-Host ""
    Write-Host "Step 4: Creating outages dataframe..." -ForegroundColor Yellow
    
    $createResult = py "..\create_outages_dataframe.py" -d $outputDir -u pse --latestfiles -o "..\test_resolved_current_outages.csv" 2>&1
    $createExitCode = $LASTEXITCODE
    
    if ($Verbose) {
        Write-Host "Create dataframe output:" -ForegroundColor Gray
        $createResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
    
    Write-Host "Dataframe creation completed (exit code: $createExitCode)"
    
    if ($createExitCode -eq 0) {
        # Step 5: Run analysis
        Write-Host ""
        Write-Host "Step 5: Running outage analysis..." -ForegroundColor Yellow
        
        # Build analyze command with optional Telegram parameters
        $analyzeCmd = "py `"..\analyze_current_outages.py`" -u pse -f `"..\test_resolved_current_outages.csv`" -l 6 -c 100 -e 0.25 --notification-output-dir `"output`""
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
        
        Write-Host "Analysis completed (exit code: $analysisExitCode)"
        
        # Step 6: Validate notification results
        Write-Host ""
        Write-Host "Step 6: Validating notification results..." -ForegroundColor Yellow
        
        $testsPass = 0
        $totalTests = 2
        
        # Check for resolved outage notification file - should NOT exist for below threshold scenario
        $notificationFiles = Get-ChildItem -Path "output" -Filter "notification_resolved_*.txt" -ErrorAction SilentlyContinue
        if ($notificationFiles.Count -eq 0) {
            Write-Host "+ No resolved outage notification file created (as expected for below threshold scenario)" -ForegroundColor Green
            $testsPass++
        } else {
            Write-Host "- Unexpected resolved outage notification file(s) found" -ForegroundColor Red
        }
        
        # Check that no new outage notifications were created (since this is a resolved scenario)
        $newNotificationFiles = Get-ChildItem -Path "output" -Filter "notification_new_*.txt" -ErrorAction SilentlyContinue
        if ($newNotificationFiles.Count -eq 0) {
            Write-Host "+ No new outage notifications created (as expected for resolved scenario)" -ForegroundColor Green
            $testsPass++
        } else {
            Write-Host "- Unexpected new outage notifications found" -ForegroundColor Red
        }
        
        Write-Host ""
        Write-Host "=== Test Results ===" -ForegroundColor Cyan
        Write-Host "Tests passed: $testsPass / $totalTests" -ForegroundColor $(if ($testsPass -eq $totalTests) { "Green" } else { "Yellow" })
        
        if ($testsPass -eq $totalTests) {
            Write-Host ""
            Write-Host "Resolved Outage Below Threshold Test PASSED!" -ForegroundColor Green
            Write-Host "The pipeline correctly did not send notifications for a resolved outage that did not meet thresholds." -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "Resolved Outage Below Threshold Test FAILED!" -ForegroundColor Red
            Write-Host "Notification verification failed - unexpected notifications were sent for an outage that should not have met thresholds." -ForegroundColor Red
        }
    } else {
        throw "create_outages_dataframe.py failed with exit code $createExitCode"
    }
    
} catch {
    Write-Host ""
    Write-Host "✗ Test FAILED!" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
} finally {
    # Always restore original git_mock.py
    if (Test-Path "git_mock.py.backup") {
        Copy-Item "git_mock.py.backup" "git_mock.py" -Force
        Remove-Item "git_mock.py.backup" -Force -ErrorAction SilentlyContinue
        if ($Verbose) {
            Write-Host "Restored original git_mock.py" -ForegroundColor Gray
        }
    }
    
    if (!$KeepFiles) {
        Write-Host ""
        Write-Host "Cleaning up test files..." -ForegroundColor Gray
        
        # Clean up test files
        Remove-Item -Path "output\test_resolved_output" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "output\test_resolved_current_outages.csv" -Force -ErrorAction SilentlyContinue

        Remove-Item -Path "output\notification_resolved_*.txt" -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host ""
        Write-Host "Keeping test files for debugging..." -ForegroundColor Yellow
    }
}
