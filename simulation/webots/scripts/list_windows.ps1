Get-Process | Where-Object { $_.MainWindowTitle -ne "" } | ForEach-Object {
    Write-Output "PID: $($_.Id) | Name: $($_.ProcessName) | Title: $($_.MainWindowTitle)"
}
