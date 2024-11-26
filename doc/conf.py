# ruff: noqa: D100
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
import os
import importlib.metadata
import warnings
from packaging.version import Version

project = 'sentinel'
copyright = '2024, William D. Jones'
author = 'William D. Jones'
release = '0.1.0'

# Don't hide DeprecationWarnings:
# https://docs.python.org/3/library/warnings.html#overriding-the-default-filter
warnings.simplefilter("default")

try:
    sent_ver = Version(importlib.metadata.version("sentinel"))
    am_ver = Version(importlib.metadata.version("amaranth"))
except importlib.metadata.PackageNotFoundError as e:
    msg = "run \"pdm install --dev -G dev -G doc\" before building docs"
    raise RuntimeError(msg) from e

if am_ver.is_devrelease:
    # If I get "(exception: '<' not supported between instances of 'dict' and
    # 'dict')", it's because of this:
    # https://github.com/sphinx-doc/sphinx/issues/11466
    # We'll have to remove the docs manually for now...
    am_ver = "latest"
else:
    am_ver = f"v{am_ver.public}"

# https://github.com/amaranth-lang/amaranth/commit/e356ee2cac1f4b12339cd1a16f328510e6407b87
version = str(sent_ver).replace(".editable", "")
release = sent_ver.public
author = 'William D. Jones'

sys.path.append(os.path.abspath('../src'))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser",
              "sphinx.ext.autodoc",
              "sphinx.ext.intersphinx",
              "sphinx_rtd_theme",
              "sphinx.ext.doctest",
              "sphinx.ext.napoleon",
              "sphinx.ext.todo",
              "sphinx_prompt"]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

intersphinx_mapping = {'python': ('https://docs.python.org/3', None),
                       'amaranth': (f'https://amaranth-lang.org/docs/amaranth/{am_ver}/', None)}  # noqa: E501
autodoc_default_options = {"members": True,
                           "undoc-members": True}
todo_include_todos = True
napoleon_custom_sections = ["Registers"]

myst_footnote_transition = False
myst_heading_anchors = 3
myst_enable_extensions = ["deflist"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']
html_theme_options = {
    'navigation_depth': 5
}
