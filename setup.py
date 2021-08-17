from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pdfls',
    version='0.1',
    description='pdfls is a small utility to debug a PDF file.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/metebalci/pdfls',
    author='Mete Balci',
    author_email='metebalci@gmail.com',
    license='GPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
	'Environment :: Console',
	'Intended Audience :: Science/Research',
	'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
	'Topic :: Utilities',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='pdf',
    py_modules=['pdfls'],
    install_requires=['pdfminer.six>=20201018'],

    entry_points={
        'console_scripts': [
            'pdfls=pdfls:run',
        ],
    },
)
