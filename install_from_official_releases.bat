
echo Install EnOcean Device Manager (eo-man) from official releases

echo Check if Python is installed.
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python is installed.
) else (
    echo Python is not installed or not working.
    pause
    exit
)

:: Set directory
set "directory=installed_official_eo_man"
echo Use folder $directory to install eo-man

:: Create a virtual environment
echo Creating a virtual environment...
python.exe -m venv %directory%

:: Activate the virtual environment
call .\%directory%\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install eo_man
echo Install EnOcean Device Manager (eo-man)
pip.exe install eo_man

if %ERRORLEVEL% neq 0 (
    echo Failed to install EnOcean Device Manager.
    exit /b
)

set script_directory=%~dp0

echo Generate execution file to start eo-man
echo @echo off > .\%directory%\eo_man.bat
echo START "eo-man" %script_directory%\%directory%\Scripts\pythonw.exe -m eo_man >> .\%directory%\eo_man.bat

echo Generate execution file to update eo-man
echo @echo off > %script_directory%\%directory%\update_eo_man.bat
echo START "eo-man" %script_directory%\%directory%\Scripts\pip.exe install eo_man --upgrade >> .\%directory%\update_eo_man.bat

echo Installation complete!

echo Run %directory%\eo-man.bat to start eo-man
cd %script_directory%\%directory%
call .\eo_man.bat