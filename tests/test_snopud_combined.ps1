# SNOPUD Combined Outages Test
# Tests the scenario where two SNOPUD placemarks have the same start time
# and should be combined into a single outage with aggregated data.
#
# Parameters:
#   -Verbose: Show detailed output from each step
#   -KeepFiles: Don't clean up test files after completion

param(
    [switch]$Verbose,
    [switch]$KeepFiles
)

Write-Host "🧪 SNOPUD Combined Outages Test" -ForegroundColor Cyan
Write-Host ""

# Use relative paths to reference production scripts

try {
    # Step 1: Set up combined outages scenario
    Write-Host "Step 1: Setting up combined outages scenario..." -ForegroundColor Yellow
    
    # Backup original git_mock.py
    Copy-Item "git_mock.py" "git_mock.py.backup" -Force
    
    # Modify git_mock.py to import from test_data_snopud_combined for this scenario
    $gitMockContent = Get-Content "git_mock.py" -Raw
    $modifiedContent = $gitMockContent -replace 'from test_data import get_default_mock_data as get_test_data', 'from test_data_snopud_combined import get_default_mock_data as get_test_data'
    
    Set-Content "git_mock.py" $modifiedContent -Encoding UTF8
    
    # Step 2: Run expand.py with mock flag
    Write-Host "Step 2: Running expand.py with --mock..." -ForegroundColor Yellow
    
    # Create output directory
    $outputDir = "test_output_snopud_combined"
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
        
        $createResult = py ..\create_outages_dataframe.py -d $outputDir -u snopud --latestfiles -o "$outputDir\test_snopud_combined_outages.csv" 2>&1
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
            
            $csvFile = "$outputDir\test_snopud_combined_outages.csv"
            Write-Host "CSV file: $csvFile" -ForegroundColor Green
            if (Test-Path $csvFile) {
                Write-Host "+ CSV output file created successfully" -ForegroundColor Green
                
                # Read and analyze the CSV content
                [object[]]$csvContent = Import-Csv $csvFile
                Write-Host "+ Found $($csvContent.Count) outage records in CSV" -ForegroundColor Green
                
                # Expected: 1 combined outage (same start time)
                if ($csvContent.Count -eq 1) {
                    Write-Host "+ Test PASSED: Found exactly 1 combined outage as expected" -ForegroundColor Green
                    
                    $outage = $csvContent[0]
                    
                    # Check customer count (should be sum of both placemarks: 5 + 3 = 8)
                    $customerCount = [int]$outage.customers_impacted
                    if ($customerCount -eq 8) {
                        Write-Host "+ Test PASSED: Customer count correctly aggregated (5 + 3 = 8)" -ForegroundColor Green
                    } else {
                        Write-Host "- Test FAILED: Expected customer count 8, got $customerCount" -ForegroundColor Red
                    }
                    
                    # Check start time (should be the same for both original placemarks)
                    $startTime = $outage.start_time
                    Write-Host "+ Start time: $startTime" -ForegroundColor Green
                    
                    # Check outage ID (should use first placemark name)
                    $outageId = $outage.outage_id
                    if ($outageId -like "*6207*") {
                        Write-Host "+ Test PASSED: Outage ID uses first placemark name (6207)" -ForegroundColor Green
                    } else {
                        Write-Host "- Test FAILED: Outage ID should use first placemark name" -ForegroundColor Red
                    }
                    
                    # Check cause (should be same for both)
                    $cause = $outage.cause
                    Write-Host "+ Cause: $cause" -ForegroundColor Green
                    
                    # Check status (should be same for both)
                    $status = $outage.status
                    Write-Host "+ Status: $status" -ForegroundColor Green
                    
                } else {
                    Write-Host "- Test FAILED: Expected 1 combined outage, found $($csvContent.Count)" -ForegroundColor Red
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
            "test_output_snopud_combined"
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
