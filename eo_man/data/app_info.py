import os

class ApplicationInfo():

    app_info:dict[str:str]=None

    @classmethod
    def get_app_info(cls):
        
        if not cls.app_info:
            filename = None
            parent_folder = os.path.join(os.path.dirname(__file__), '..', '..')
            for f in os.listdir(parent_folder):
                if os.path.isdir(f):
                    if f.startswith('eo_man-') and f.endswith('.dist-info'):
                        filename = os.path.join(parent_folder, f, 'METADATA')
                        break
                    if 'eo_man.egg-info' in f:
                        filename = os.path.join(parent_folder, f, 'PKG-INFO')
                        break
            
            app_info = {}
            if filename and os.path.isfile(filename):
                with open(filename, 'r', encoding='utf-8') as file:
                    for l in file.readlines():
                        if l.startswith('Name:'):
                            app_info['name'] = l.split(':')[1].strip()
                        elif l.startswith('Version:'):
                            app_info['version'] = l.split(':')[1].strip()
                        elif l.startswith('Summary:'):
                            app_info['summary'] = l.split(':')[1].strip()
                        elif l.startswith('Home-page:'):
                            app_info['home-page'] = l.split(':')[1].strip()
                        elif l.startswith('Author:'):
                            app_info['author'] = l.split(':')[1].strip()
                        elif l.startswith('License:'):
                            app_info['license'] = l.split(':')[1].strip()
                        elif l.startswith('Requires-Python:'):
                            app_info['requires-python'] = l.split(':')[1].strip()
            
        return app_info
                        
    @classmethod
    def get_app_info_as_str(cls) -> str:
        result = ''
        for k, v in cls.get_app_info().items():
            result += f"{k.title()}: {v}\n"
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