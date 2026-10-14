# Send a file's bytes untouched to a Windows printer queue (RAW datatype), the way
# a receipt printer's driver expects ESC/POS. Used by system.mjs on Windows.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File win-raw-print.ps1 -PrinterName "EPSON TM-T20III Receipt" -FilePath job.bin -DocName "Receipt"
param(
	[Parameter(Mandatory = $true)][string]$PrinterName,
	[Parameter(Mandatory = $true)][string]$FilePath,
	[string]$DocName = "Sales App"
)
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class SalesAppRawPrinter
{
	[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
	public class DOCINFOW
	{
		[MarshalAs(UnmanagedType.LPWStr)] public string pDocName;
		[MarshalAs(UnmanagedType.LPWStr)] public string pOutputFile;
		[MarshalAs(UnmanagedType.LPWStr)] public string pDataType;
	}

	[DllImport("winspool.Drv", EntryPoint = "OpenPrinterW", SetLastError = true, CharSet = CharSet.Unicode, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool OpenPrinter([MarshalAs(UnmanagedType.LPWStr)] string szPrinter, out IntPtr hPrinter, IntPtr pd);
	[DllImport("winspool.Drv", EntryPoint = "ClosePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool ClosePrinter(IntPtr hPrinter);
	[DllImport("winspool.Drv", EntryPoint = "StartDocPrinterW", SetLastError = true, CharSet = CharSet.Unicode, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool StartDocPrinter(IntPtr hPrinter, Int32 level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOW di);
	[DllImport("winspool.Drv", EntryPoint = "EndDocPrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool EndDocPrinter(IntPtr hPrinter);
	[DllImport("winspool.Drv", EntryPoint = "StartPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool StartPagePrinter(IntPtr hPrinter);
	[DllImport("winspool.Drv", EntryPoint = "EndPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool EndPagePrinter(IntPtr hPrinter);
	[DllImport("winspool.Drv", EntryPoint = "WritePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
	public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, Int32 dwCount, out Int32 dwWritten);

	public static int Send(string printerName, byte[] bytes, string docName)
	{
		IntPtr hPrinter;
		if (!OpenPrinter(printerName, out hPrinter, IntPtr.Zero)) return -Marshal.GetLastWin32Error();
		try
		{
			DOCINFOW di = new DOCINFOW();
			di.pDocName = docName;
			di.pDataType = "RAW";
			if (!StartDocPrinter(hPrinter, 1, di)) return -Marshal.GetLastWin32Error();
			try
			{
				if (!StartPagePrinter(hPrinter)) return -Marshal.GetLastWin32Error();
				IntPtr unmanaged = Marshal.AllocCoTaskMem(bytes.Length);
				try
				{
					Marshal.Copy(bytes, 0, unmanaged, bytes.Length);
					int written;
					if (!WritePrinter(hPrinter, unmanaged, bytes.Length, out written)) return -Marshal.GetLastWin32Error();
					EndPagePrinter(hPrinter);
					return written;
				}
				finally { Marshal.FreeCoTaskMem(unmanaged); }
			}
			finally { EndDocPrinter(hPrinter); }
		}
		finally { ClosePrinter(hPrinter); }
	}
}
"@

$bytes = [System.IO.File]::ReadAllBytes($FilePath)
$result = [SalesAppRawPrinter]::Send($PrinterName, $bytes, $DocName)
if ($result -lt 0) {
	$code = -$result
	$message = (New-Object System.ComponentModel.Win32Exception($code)).Message
	Write-Error "Windows refused the job for '$PrinterName': $message (error $code)"
	exit 1
}
if ($result -ne $bytes.Length) {
	Write-Error "Only $result of $($bytes.Length) bytes reached '$PrinterName'"
	exit 1
}
Write-Output "$result bytes sent to $PrinterName"
