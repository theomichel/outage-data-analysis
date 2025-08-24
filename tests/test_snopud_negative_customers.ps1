# SNOPUD Negative Customers Test
# Tests the scenario where the previous snapshot has an outage with -1 affected customers
# and the current snapshot has an outage with 101 affected customers.
# The -1 outage should be skipped, and only the current snapshot should be processed.
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
    [string]$TelegramThreadId = $null
)

Write-Host "🧪 SNOPUD Negative Customers Test" -ForegroundColor Cyan
Write-Host ""

# Log Telegram notification status
if ($TelegramToken -and $TelegramChatId) {
    Write-Host "Telegram notifications: ENABLED (Chat ID: $TelegramChatId)" -ForegroundColor Green
} else {
    Write-Host "Telegram notifications: DISABLED" -ForegroundColor Yellow
}
Write-Host ""

# Use relative paths to reference production scripts

try {
    # Step 1: Set up negative customers scenario
    Write-Host "Step 1: Setting up negative customers scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "git_mock.py" "git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_snopud_negative_customers for this scenario
    $gitMockContent = Get-Content "git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_snopud_negative_customers import get_default_mock_data as get_test_data'
    
    Set-Content "git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "test_output_snopud_negative_customers"
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    
    $expandResult = py ..\expand.py --mock -i -o $outputDir -l 10 ..\KMLOutageAreas.xml 2>&1
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
    $exportedFiles = Get-ChildItem $outputDir -Filter "*.xml" | Sort-Object Name
    
    if ($exportedFiles.Count -gt 0) {
        Write-Host "+ Found $($exportedFiles.Count) exported files:" -ForegroundColor Green
        $exportedFiles | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }
    } else {
        Write-Host "- No exported files found" -ForegroundColor Red
    }
    
    # Step 4: Run create_outages_dataframe.py on the mock data
    if ($exportedFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "Step 4: Creating outages dataframe..." -ForegroundColor Yellow
        
        $createResult = py ..\create_outages_dataframe.py -d $outputDir -u snopud --latestfiles -o "$outputDir\test_snopud_negative_customers_outages.csv" 2>&1
        $createExitCode = $LASTEXITCODE
        
        if ($Verbose) {
            Write-Host "Create dataframe output:" -ForegroundColor Gray
            $createResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        }
        
        Write-Host "Dataframe creation completed (exit code: $createExitCode)" -ForegroundColor $(if ($createExitCode -eq 0) {"Green"} else {"Red"})
        
        # Step 5: Run analyze_current_outages.py
        if ($createExitCode -eq 0) {
            Write-Host ""
            Write-Host "Step 5: Running analyze_current_outages.py..." -ForegroundColor Yellow
            
                         # Build analyze command with optional Telegram parameters
             $analyzeCmd = "py ..\analyze_current_outages.py -f `"$outputDir\test_snopud_negative_customers_outages.csv`" -u snopud -l 0.5 -c 50 -e 0.5"
             if ($TelegramToken -and $TelegramChatId) {
                 $analyzeCmd += " --telegram-token `"$TelegramToken`" --telegram-chat-id `"$TelegramChatId`""
                 if ($TelegramThreadId) {
                     $analyzeCmd += " --telegram-thread-id `"$TelegramThreadId`""
                 }
             }
             
             $analyzeResult = Invoke-Expression $analyzeCmd 2>&1
            $analyzeExitCode = $LASTEXITCODE
            
            if ($Verbose) {
                Write-Host "Analyze output:" -ForegroundColor Gray
                $analyzeResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
            
            Write-Host "Analysis completed (exit code: $analyzeExitCode)" -ForegroundColor $(if ($analyzeExitCode -eq 0) {"Green"} else {"Red"})
            
            # Step 6: Validate results
            if ($analyzeExitCode -eq 0) {
                Write-Host ""
                Write-Host "Step 6: Validating results..." -ForegroundColor Yellow
                
                # Check the original CSV file
                $csvFile = "$outputDir\test_snopud_negative_customers_outages.csv"
                if (Test-Path $csvFile) {
                    Write-Host "+ Original CSV output file created successfully" -ForegroundColor Green
                    
                    # Read and analyze the CSV content
                    [object[]]$csvContent = Import-Csv $csvFile
                    Write-Host "+ Found $($csvContent.Count) outage records in original CSV" -ForegroundColor Green
                    
                    # Expected: 1 outage from current snapshot (previous -1 outage should be skipped)
                    if ($csvContent.Count -eq 1) {
                        Write-Host "+ Test PASSED: Found exactly 1 outage as expected" -ForegroundColor Green
                        
                        $outage = $csvContent[0]
                        
                        # Check customer count (should be 101 from current snapshot)
                        $customerCount = [int]$outage.customers_impacted
                        if ($customerCount -eq 101) {
                            Write-Host "+ Test PASSED: Customer count correct (101)" -ForegroundColor Green
                        } else {
                            Write-Host "- Test FAILED: Expected customer count 101, got $customerCount" -ForegroundColor Red
                        }
                        
                        # Check start time
                        $startTime = $outage.start_time
                        Write-Host "+ Start time: $startTime" -ForegroundColor Green
                        
                                                 # Check outage ID (should be timestamp-based from start time)
                         $outageId = $outage.outage_id
                         if ($outageId -eq "20250115132642") {
                             Write-Host "+ Test PASSED: Outage ID uses timestamp format (20250115132642)" -ForegroundColor Green
                         } else {
                             Write-Host "- Test FAILED: Expected outage ID 20250115132642, got $outageId" -ForegroundColor Red
                         }
                        
                        # Check utility
                        $utility = $outage.utility
                        if ($utility -eq "snopud") {
                            Write-Host "+ Test PASSED: Utility correctly set to 'snopud'" -ForegroundColor Green
                        } else {
                            Write-Host "- Test FAILED: Utility should be 'snopud', got '$utility'" -ForegroundColor Red
                        }
                        
                    } else {
                        Write-Host "- Test FAILED: Expected 1 outage, found $($csvContent.Count)" -ForegroundColor Red
                    }
                } else {
                    Write-Host "- Test FAILED: Original CSV output file not created" -ForegroundColor Red
                }
                
                # Check the analysis CSV file
                $analysisFile = "snopud_current_outages_analysis.csv"
                if (Test-Path $analysisFile) {
                    Write-Host "+ Analysis CSV file created successfully" -ForegroundColor Green
                    
                    # Read and analyze the analysis CSV content
                    [object[]]$analysisContent = Import-Csv $analysisFile
                    Write-Host "+ Found $($analysisContent.Count) outage records in analysis CSV" -ForegroundColor Green
                    
                    # Expected: 1 outage that meets the thresholds (101 customers > 50 threshold)
                    if ($analysisContent.Count -eq 1) {
                        Write-Host "+ Test PASSED: Found exactly 1 outage meeting analysis thresholds" -ForegroundColor Green
                        
                        $analysisOutage = $analysisContent[0]
                        
                        # Check customer count in analysis (should be 101)
                        $analysisCustomerCount = [int]$analysisOutage.customers_impacted
                        if ($analysisCustomerCount -eq 101) {
                            Write-Host "+ Test PASSED: Analysis customer count correct (101)" -ForegroundColor Green
                        } else {
                            Write-Host "- Test FAILED: Expected analysis customer count 101, got $analysisCustomerCount" -ForegroundColor Red
                        }
                        
                                                 # Check that elapsed time meets threshold (should be > 0.5 hours)
                         $elapsedHours = [double]$analysisOutage.elapsed_time_minutes / 60
                         if ($elapsedHours -gt 0.5) {
                             Write-Host "+ Test PASSED: Elapsed time meets threshold ($elapsedHours hours > 0.5)" -ForegroundColor Green
                         } else {
                             Write-Host "- Test FAILED: Elapsed time should be > 0.5 hours, got $elapsedHours" -ForegroundColor Red
                         }
                         
                     } else {
                         Write-Host "- Test FAILED: Expected 1 outage in analysis, found $($analysisContent.Count) in $analysisFile" -ForegroundColor Red
                     }
                 } else {
                     Write-Host "- Test FAILED: Analysis CSV file not created" -ForegroundColor Red
                 }
                 
                 # Check for notification files
                 $notificationFiles = Get-ChildItem -Filter "notification_*.txt" | Sort-Object Name
                 if ($notificationFiles.Count -gt 0) {
                     Write-Host "+ Test PASSED: Found $($notificationFiles.Count) notification file(s)" -ForegroundColor Green
                     
                     # Check that we have a "new" notification for the outage
                     $newNotification = $notificationFiles | Where-Object { $_.Name -like "*new*" }
                     if ($newNotification) {
                         Write-Host "+ Test PASSED: Found new outage notification" -ForegroundColor Green
                         
                                                   # Read the notification content to verify it's correct
                          $notificationContent = Get-Content $newNotification.FullName -Raw
                          if ($notificationContent -like "*20250115132642*") {
                              Write-Host "+ Test PASSED: Notification contains correct outage ID (20250115132642)" -ForegroundColor Green
                          } else {
                              Write-Host "- Test FAILED: Notification should contain outage ID 20250115132642" -ForegroundColor Red
                          }
                         
                         if ($notificationContent -like "*101*") {
                             Write-Host "+ Test PASSED: Notification contains correct customer count (101)" -ForegroundColor Green
                         } else {
                             Write-Host "- Test FAILED: Notification should contain customer count 101" -ForegroundColor Red
                         }
                         
                         if ($notificationContent -like "*SNOPUD*") {
                             Write-Host "+ Test PASSED: Notification contains correct utility name (SNOPUD)" -ForegroundColor Green
                         } else {
                             Write-Host "- Test FAILED: Notification should contain utility name SNOPUD" -ForegroundColor Red
                         }
                         
                     } else {
                         Write-Host "- Test FAILED: Should have a new outage notification" -ForegroundColor Red
                     }
                     
                     # List all notification files for debugging
                     Write-Host "+ Notification files created:" -ForegroundColor Gray
                     $notificationFiles | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }
                     
                 } else {
                     Write-Host "- Test FAILED: No notification files created" -ForegroundColor Red
                 }
                
            } else {
                Write-Host "- Analysis failed, skipping validation" -ForegroundColor Red
            }
        } else {
            Write-Host "- Dataframe creation failed, skipping analysis" -ForegroundColor Red
        }
    } else {
        Write-Host "- No exported files for analysis" -ForegroundColor Red
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
        if (Test-Path "git_mock.py.backup") {
            Move-Item "git_mock.py.backup" "git_mock.py" -Force
        }
        
                 # Remove test files
         $filesToRemove = @(
             "test_output_snopud_negative_customers",
             "snopud_current_outages_analysis.csv"
         )
         
         # Also remove notification files
         $notificationFiles = Get-ChildItem -Filter "notification_*.txt" -ErrorAction SilentlyContinue
         foreach ($file in $notificationFiles) {
             Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
             Write-Host "  Removed: $($file.Name)" -ForegroundColor Gray
         }
        
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
