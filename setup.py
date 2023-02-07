from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in digital_printing/__init__.py
from digital_printing import __version__ as version

setup(
	name="digital_printing",
	version=version,
	description="Digital Printing ERP Application",
	author="ParaLogic",
	author_email="info@paralogic.io",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
