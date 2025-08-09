# Archived: Windows Task Scheduler setup (use GitHub Actions cron instead)
# Original content preserved for future local/on-prem scheduling

# PowerShell script to create a Windows Task Scheduler job for the trading agent
# Run this script as Administrator

$TaskName = "DST-Trading-Agent"
$ScriptPath = "c:\Users\Petra\.vscode\vscode_projects\dst-agent\main.py"
$PythonPath = "python"  # Adjust if Python is in a different location
$WorkingDirectory = "c:\Users\Petra\.vscode\vscode_projects\dst-agent"

# Delete existing task if it exists
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed existing task: $TaskName"
}
catch {
    Write-Host "No existing task to remove"
}

# Create the action (what to run)
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory $WorkingDirectory

# Create the trigger (when to run) - Daily at 1:00 PM
$Trigger = New-ScheduledTaskTrigger -Daily -At "13:00"

# Create task settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Create the principal (run as current user)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Register the scheduled task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Daily stock trading analysis report - runs before US market opens"
    Write-Host "✅ Successfully created scheduled task: $TaskName"
    Write-Host "📅 Scheduled to run daily at 1:00 PM Irish time"
    Write-Host "📍 Working directory: $WorkingDirectory"
    Write-Host "🐍 Python script: $ScriptPath"
    Write-Host ""
    Write-Host "You can:"
    Write-Host "- View the task in Task Scheduler (taskschd.msc)"
    Write-Host "- Run it manually: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "- Check status: Get-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Host "❌ Failed to create scheduled task: $($_.Exception.Message)"
    Write-Host "Make sure you're running PowerShell as Administrator"
}

# Display next run time
try {
    $Task = Get-ScheduledTask -TaskName $TaskName
    $NextRun = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
    Write-Host "⏰ Next scheduled run: $NextRun"
}
catch {
    Write-Host "Could not determine next run time"
}
