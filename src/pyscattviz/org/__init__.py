"""Orgs: a data folder of reduced scattering frames, read, linked and kept.

:mod:`~pyscattviz.org.layouts`  how a folder is read into one row per frame
:mod:`~pyscattviz.org.cms`      the CMS experiment layout, and what the pages
                                share: sample tables, runs, curves
:mod:`~pyscattviz.org.store`    making, opening and keeping an org (pyDataOrg)
:mod:`~pyscattviz.org.ask`      Ask AI: questions about an org, and a
                                proposal of how to read a folder

None of these needs Streamlit to be running; only :mod:`store` needs
pyDataOrg (``pip install "pyScattViz[org]"``).
"""
