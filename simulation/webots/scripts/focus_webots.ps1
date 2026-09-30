$sig = @'
using System;
using System.Runtime.InteropServices;
public class WindowHelper {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
'@
Add-Type -TypeDefinition $sig
$procs = Get-Process -Name "msrdc" -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    if ($p.MainWindowTitle -like "*warehouse_fl*" -or $p.MainWindowTitle -like "*webots*") {
        Write-Output "Found Webots window: $($p.MainWindowTitle) (PID: $($p.Id))"
        [WindowHelper]::ShowWindow($p.MainWindowHandle, 9) # 9 = SW_RESTORE
        [WindowHelper]::SetForegroundWindow($p.MainWindowHandle)
        Write-Output "Successfully brought to foreground."
    }
}
