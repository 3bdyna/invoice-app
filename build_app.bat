@echo off
echo ===================================
echo Building Invoice System Application
echo ===================================
echo.
echo Installing required packages...
pip install pyinstaller fpdf2 qrcode pillow arabic-reshaper python-bidi tkcalendar

echo.
echo Creating executable...

:: Note: --add-data "SOURCE;DESTINATION" (Windows uses semicolon separator)
:: We are bundling 'arabic_font.ttf' from the local 'fonts' folder into the 'fonts' folder inside the PyInstaller temporary runtime directory.

pyinstaller --onefile --windowed --name "Invoice System" ^
  --add-data "fonts\arabic_font.ttf;fonts" ^
  --hidden-import=arabic_reshaper ^
  --hidden-import=bidi.algorithm ^
  --hidden-import=qrcode ^
  --hidden-import=fpdf ^
  --hidden-import=tkcalendar ^
  main.py

echo.
echo Build complete! Check the "dist" folder for your executable.
echo.
pause