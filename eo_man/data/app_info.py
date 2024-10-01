import os
import tomli
import requests

class ApplicationInfo():

    app_info:dict[str:str]=None
    pypi_info_latest_versino:dict=None
    pypi_info_current_version:dict=None

    @classmethod
    def get_app_info(cls, filename:str=None):
        
        if not cls.app_info:

            app_info = {}
            parent_folder = os.path.join(os.path.dirname(__file__), '..')
            pyproject_file = os.path.join(parent_folder, 'pyproject.toml')
            if not os.path.isfile(pyproject_file):
                pyproject_file = os.path.join(parent_folder, '..', 'pyproject.toml')
                if not os.path.isfile(pyproject_file):
                    pyproject_file = None
                
            if pyproject_file:
                with open(pyproject_file, "rb") as f:
                    pyproject_data = tomli.load(f)
                app_info['version'] = pyproject_data["project"]["version"]
                app_info['name'] = pyproject_data["project"]["name"]
                app_info['author'] = ', '.join([ f"{a.get('name')} {a.get('email', '')}".strip() for a in pyproject_data["project"]["authors"]])
                app_info['home-page'] = pyproject_data["project"]["urls"]["Homepage"]
                app_info['license'] = pyproject_data["project"]["license"]["text"]

            if not filename:
                parent_folder = os.path.join(os.path.dirname(__file__), '..', '..')
                for f in os.listdir(parent_folder):
                    if os.path.isdir(os.path.join(parent_folder, f)):
                        # for installed package => get info from package metadata folder
                        if f.startswith('eo_man-') and f.endswith('.dist-info'):
                            filename = os.path.join(parent_folder, f, 'METADATA')
                            break
                        # for development environment => get info from built package (needs to be built first)
                        if 'eo_man.egg-info' in f:
                            filename = os.path.join(parent_folder, f, 'PKG-INFO')
                            break
            
            if filename and os.path.isfile(filename):
                with open(filename, 'r', encoding='utf-8') as file:
                    for l in file.readlines():
                        if l.startswith('Name:'):
                            app_info['name'] = l.split(':',1)[1].strip()
                        elif l.startswith('Version:'):
                            app_info['version'] = l.split(':',1)[1].strip()
                        elif l.startswith('Summary:'):
                            app_info['summary'] = l.split(':',1)[1].strip()
                        elif l.startswith('Home-page:'):
                            app_info['home-page'] = l.split(':',1)[1].strip()
                        elif l.startswith('Author:'):
                            app_info['author'] = l.split(':',1)[1].strip()
                        elif l.startswith('License:'):
                            app_info['license'] = l.split(':',1)[1].strip()
                        elif l.startswith('Requires-Python:'):
                            app_info['requires-python'] = l.split(':',1)[1].strip()

            
            # get latest version
            cls.pypi_info_latest_versino = cls._get_info_from_pypi()
            app_info['lastest_available_version'] = cls.pypi_info_latest_versino.get('info', {}).get('version', None)
            # get current/installed version
            if app_info['version'] is not None and app_info['version'] != '':
                cls.pypi_info_current_version = cls._get_info_from_pypi(app_info['version'])

            cls.app_info = app_info
            
        return cls.app_info
                        
    @classmethod
    def _get_info_from_pypi(cls, version:str=''):
        if version is not None and version != '':
            if not version.startswith('/') and not version.endswith('/'):
                version = version + '/'

        url = f"https://pypi.org/pypi/eo-man/{version}json"

        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
            
        return {}


    @classmethod
    def get_app_info_as_str(cls, separator:str='\n', prefix:str='') -> str:
        result = ''
        for k, v in cls.get_app_info().items():
            result += f"{prefix}{k.title()}: {v}{separator}"
        return result

    @classmethod
    def get_package_name(cls) -> str:
        return cls.get_app_info().get('name', 'unknown')
    
    @classmethod
    def get_version(cls) -> str:
        return cls.get_app_info().get('version', 'unknown')

    @classmethod
    def get_summary(cls) -> str:
        return cls.get_app_info().get('summery', 'unknown')
    
    @classmethod
    def get_home_page(cls) -> str:
        return cls.get_app_info().get('home-page', 'unknown')
    
    @classmethod
    def get_author(cls) -> str:
        return cls.get_app_info().get('author', 'unknown')
    
    @classmethod
    def get_license(cls) -> str:
        return cls.get_app_info().get('license', 'unknown')

    @classmethod
    def get_requires_python(cls) -> str:
        return cls.get_app_info().get('requires-python', 'unknown')
    
    @classmethod
    def get_lastest_available_version(cls) -> str:
        return cls.get_app_info().get('lastest_available_version', 'unknown')

    @classmethod
    def is_version_up_to_date(cls) -> bool:
        cv = cls.get_app_info().get('version', '0.0.0') 
        lv = cls.pypi_info_latest_versino['info']['version']

        for i in range(0,3):
            l = int(lv.split('.')[i])
            c = int(cv.split('.')[i])
            if l > c:
                return False
            elif c > l:
                return True
        return True