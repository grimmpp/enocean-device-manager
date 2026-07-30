"""Checks that requirements.txt and pyproject.toml declare the same dependencies.

requirements.txt is what a developer installs when the application is run
directly out of the repository, the dependencies of pyproject.toml are what a
user gets when the package is installed. If the two drift apart, the released
package pulls other versions than the ones the application was tested with.

requirements.txt may contain additional entries which are only needed to work
with the repository itself (see REQUIREMENTS_ONLY). Everything else has to be
declared in both files with the same version.
"""

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REQUIREMENTS_TXT = PROJECT_ROOT / 'requirements.txt'
PYPROJECT_TOML = PROJECT_ROOT / 'pyproject.toml'

# Entries which are needed to run the application from the repository and to run
# the tests, but which must not be dependencies of the installed package.
REQUIREMENTS_ONLY = {
    'tk',           # tkinter is part of the python installation of the user
    'pytest',       # only needed to run the tests
}

# characters a version specifier can start with (==, >=, <=, ~=, !=, >, <, ===)
SPECIFIER_START = '=<>!~'


def normalize_name(name: str) -> str:
    """Package names are compared case insensitively and '-', '_' and '.' are
    equivalent (PEP 503)."""
    return name.strip().lower().replace('_', '-').replace('.', '-')


def split_requirement(requirement: str) -> tuple:
    """Splits e.g. 'pillow>=11' into ('pillow', '>=11')."""
    for i, char in enumerate(requirement):
        if char in SPECIFIER_START:
            return normalize_name(requirement[:i]), requirement[i:].replace(' ', '')
    return normalize_name(requirement), ''


def read_requirements_txt() -> dict:
    # the file starts with a BOM, utf-8-sig removes it
    lines = REQUIREMENTS_TXT.read_text(encoding='utf-8-sig').splitlines()
    entries = [line.split('#')[0].strip() for line in lines]
    return dict(split_requirement(e) for e in entries if e)


def read_pyproject_dependencies() -> dict:
    with PYPROJECT_TOML.open('rb') as f:
        pyproject = tomllib.load(f)
    return dict(split_requirement(d) for d in pyproject['project']['dependencies'])


def test_every_dependency_of_pyproject_is_in_requirements():
    requirements = read_requirements_txt()
    dependencies = read_pyproject_dependencies()

    missing = sorted(set(dependencies) - set(requirements))

    assert not missing, f"Dependencies of pyproject.toml which are missing in requirements.txt: {missing}"


def test_every_requirement_is_a_dependency_of_pyproject():
    requirements = read_requirements_txt()
    dependencies = read_pyproject_dependencies()

    missing = sorted(set(requirements) - set(dependencies) - {normalize_name(r) for r in REQUIREMENTS_ONLY})

    assert not missing, (f"Requirements which are not declared as dependency in pyproject.toml: {missing}. "
                         f"Add them there or - if they are not needed by the installed package - "
                         f"to REQUIREMENTS_ONLY of this test.")


def test_versions_are_the_same_in_both_files():
    requirements = read_requirements_txt()
    dependencies = read_pyproject_dependencies()

    differences = {name: (requirements[name], specifier)
                   for name, specifier in dependencies.items()
                   if name in requirements and requirements[name] != specifier}

    assert not differences, ("Version differs between requirements.txt and pyproject.toml "
                             f"(name: (requirements.txt, pyproject.toml)): {differences}")


def test_version_of_the_package_matches_the_change_log():
    """The topmost released version of changes.md is the one which is built."""
    with PYPROJECT_TOML.open('rb') as f:
        version = tomllib.load(f)['project']['version']

    headlines = [line for line in (PROJECT_ROOT / 'changes.md').read_text(encoding='utf-8').splitlines()
                 if line.startswith('## ')]

    assert headlines, "No release headline (## v...) found in changes.md"
    assert headlines[0].startswith(f"## v{version}"), (
        f"Version {version} of pyproject.toml does not match the newest entry of changes.md: {headlines[0]}")
