# SNOPUD Separate Outages Test
# Tests the scenario where two SNOPUD placemarks have different start times
# and should remain as separate outages.
#
# Parameters:
#   -Verbose: Show detailed output from each step
#   -KeepFiles: Don't clean up test files after completion

param(
    [switch]$Verbose,
    [switch]$KeepFiles
)

Write-Host "🧪 SNOPUD Separate Outages Test" -ForegroundColor Cyan
Write-Host ""

# Use relative paths to reference production scripts

try {
    # Step 1: Set up separate outages scenario
    Write-Host "Step 1: Setting up separate outages scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "git_mock.py" "git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_snopud_separate for this scenario
    $gitMockContent = Get-Content "git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_snopud_separate import get_default_mock_data as get_test_data'
    
    Set-Content "git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "test_output_snopud_separate"
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
        
        $createResult = py ..\create_outages_dataframe.py -d $outputDir -u snopud --latestfiles -o "$outputDir\test_snopud_separate_outages.csv" 2>&1
        $createExitCode = $LASTEXITCODE
        
        if ($Verbose) {
            Write-Host "Create dataframe output:" -ForegroundColor Gray
            $createResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        }
        
        Write-Host "Dataframe creation completed (exit code: $createExitCode)" -ForegroundColor $(if ($createExitCode -eq 0) {"Green"} else {"Red"})
        
        # Step 5: Validate results
        if ($createExitCode -eq 0) {
            Write-Host ""
            Write-Host "Step 5: Validating results..." -ForegroundColor Yellow
            
            $csvFile = "$outputDir\test_snopud_separate_outages.csv"
            if (Test-Path $csvFile) {
                Write-Host "+ CSV output file created successfully" -ForegroundColor Green
                
                # Read and analyze the CSV content
                [object[]]$csvContent = Import-Csv $csvFile
                Write-Host "+ Found $($csvContent.Count) outage records in CSV" -ForegroundColor Green
                
                # Expected: 2 separate outages (different start times)
                if ($csvContent.Count -eq 2) {
                    Write-Host "+ Test PASSED: Found exactly 2 separate outages as expected" -ForegroundColor Green
                    
                    # Check first outage (6207)
                    $outage1 = $csvContent[0]
                    $customerCount1 = [int]$outage1.customers_impacted
                    if ($customerCount1 -eq 5) {
                        Write-Host "+ Test PASSED: First outage customer count correct (5)" -ForegroundColor Green
                    } else {
                        Write-Host "- Test FAILED: Expected customer count 5 for first outage, got $customerCount1" -ForegroundColor Red
                    }
                    
                    # Check second outage (8431)
                    $outage2 = $csvContent[1]
                    $customerCount2 = [int]$outage2.customers_impacted
                    if ($customerCount2 -eq 3) {
                        Write-Host "+ Test PASSED: Second outage customer count correct (3)" -ForegroundColor Green
                    } else {
                        Write-Host "- Test FAILED: Expected customer count 3 for second outage, got $customerCount2" -ForegroundColor Red
                    }
                    
                    # Check that start times are different
                    $startTime1 = $outage1.start_time
                    $startTime2 = $outage2.start_time
                    Write-Host "+ First outage start time: $startTime1" -ForegroundColor Green
                    Write-Host "+ Second outage start time: $startTime2" -ForegroundColor Green
                    
                    if ($startTime1 -ne $startTime2) {
                        Write-Host "+ Test PASSED: Start times are different as expected" -ForegroundColor Green
                    } else {
                        Write-Host "- Test FAILED: Start times should be different" -ForegroundColor Red
                    }
                    
                } else {
                    Write-Host "- Test FAILED: Expected 2 separate outages, found $($csvContent.Count)" -ForegroundColor Red
                }
            } else {
                Write-Host "- Test FAILED: CSV output file not created" -ForegroundColor Red
            }
        } else {
            Write-Host "- Dataframe creation failed, skipping validation" -ForegroundColor Red
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
            "test_output_snopud_separate"
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
