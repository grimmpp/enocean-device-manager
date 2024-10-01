set "directory=installed_eo_man"

python.exe -m venv %directory%
.\%directory%\Scripts\pip.exe install build
.\%directory%\Scripts\pip.exe install -r requirements.txt
.\%directory%\Scripts\python.exe -m build
.\%directory%\Scripts\pip.exe install .\dist\eo_man-0.1.35-py3-none-any.whl

echo @echo off > .\%directory%\eo_man.bat
echo START "eo-man" .\Scripts\python.exe -m eo_man >> .\%directory%\eo_man.bat

.\%directory%\eo_man.bat