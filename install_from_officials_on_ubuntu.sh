sudo apt-get update
sudo apt-get install python3-venv python3-tk idel
python3 -m venv venv_eo_man
source venv_eo_man/bin/activate
python3 -m pip install eo_man

## start application
python3 -m eo_man