@echo off
echo ===================================
echo Building Invoice System Application
echo ===================================
echo.
echo Creating executable...

pyinstaller --noconfirm "Invoice System.spec"

echo.
echo Build complete! Check the "dist" folder for your executable.
echo.
pause
