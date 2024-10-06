set "directory=installed_official_eo_man"

python.exe -m venv %directory%
.\%directory%\Scripts\pip.exe install eo_man

echo @echo off > .\%directory%\eo_man.bat
echo START "eo-man" .\Scripts\pythonw.exe -m eo_man >> .\%directory%\eo_man.bat

echo @echo off > .\%directory%\update_eo_man.bat
echo START "eo-man" .\Scripts\pip.exe install eo_man --upgrade >> .\%directory%\update_eo_man.bat
