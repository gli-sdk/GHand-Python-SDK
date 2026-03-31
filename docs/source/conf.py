# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

# -- Project information -----------------------------------------------------
project = 'Xiaoyao Python SDK'
copyright = '2025, Shenzhen GLI Technology Ltd.'
author = 'glitech'
autodoc_member_order = 'bysource'

# The short X.Y version
version = '1.1'
# The full version, including alpha/beta/rc tags
release = '1.1.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
language = 'zh_CN'
exclude_patterns = []
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_logo = "images/logo.png"
html_favicon = "images/favicon.ico"
