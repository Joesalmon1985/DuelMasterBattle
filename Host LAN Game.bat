@echo off
rem DuelMasterBattle: run the world on this PC for two phones on the same Wi-Fi (the fallback when the phones cannot host).
rem Both phones: JOIN LOCAL GAME, type the join code, tap the game in the list (or type this PC's Wi-Fi address below).
rem The first phone to join gets the START THE WORLD button. Close this window to end the game.
rem If Windows asks "Allow Python to communicate on these networks", allow it on private networks (TCP 8765, UDP 8767).
setlocal
cd /d "%~dp0WizardRTSHybrid"
set "CODE=%~1"
if "%CODE%"=="" set /p "CODE=Join code for the phones (4 digits, Enter for 1234): "
if "%CODE%"=="" set "CODE=1234"
set "HYBRID_AI=1"
set "DMB_NO_NATIVE=1"
echo.
echo Hosting on this PC: join code %CODE%. The HYBRID_HOST_READY line below lists this PC's Wi-Fi addresses ("lan").
echo.
py -3 -m wizard_rts.net.host --bind 0.0.0.0 --name "%COMPUTERNAME%" --code %CODE% --seed 507 --map small --max-players 2 --first-joiner-hosts --stats-every 60
pause
