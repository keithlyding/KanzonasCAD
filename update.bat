@echo off
rem Updates KanzonasCAD to the newest tested version (main) and what it needs.
cd /d "%~dp0"
echo Updating KanzonasCAD...
git checkout main || goto failed
git pull || goto failed
py -m pip install -r requirements.txt -c constraints.txt --quiet || goto failed
echo.
echo Done. Start KanzonasCAD with KanzonasCAD.bat.
pause
exit /b 0
:failed
echo.
echo The update stopped: see the message above. README.md (If something goes wrong) explains the usual ones.
pause
exit /b 1
