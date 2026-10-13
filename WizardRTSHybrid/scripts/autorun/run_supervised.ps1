<#
 Run a long job under scripts\autorun\supervisor.py on Windows without letting the PC sleep (plan v2 11.3, 11.5).
 UNTESTED on Windows (written on the Ubuntu laptop on 13 Oct 2026): run the supervisor self-tests first
   py -3 -m pytest WizardRTSHybrid\tests\test_supervisor.py -q
 Sleep is blocked with SetThreadExecutionState for the lifetime of this script only; closing the window or ending the job restores it
 (no power plan is changed). Stop cleanly by creating  %USERPROFILE%\dmb_runs\<name>\STOP

 Example:
   .\scripts\autorun\run_supervised.ps1 -Name tourney1 -- py -3 scripts\run_civilisation_tournament.py --minutes 180 --jobs 4
#>
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Command
)
$sig = @'
[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
Add-Type -MemberDefinition $sig -Name Power -Namespace Win32
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1
[void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
try {
    if ($Command.Count -gt 0 -and $Command[0] -eq "--") { $Command = $Command[1..($Command.Count - 1)] }
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    & py -3 (Join-Path $here "supervisor.py") --name $Name -- @Command
    exit $LASTEXITCODE
}
finally {
    [void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS)  # sleep allowed again
}
