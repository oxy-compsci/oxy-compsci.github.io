#!/bin/sh

/home/justinnhli/.venv/oxy-compsci.github.io/bin/python3 backup.py && git add html md && git commit -m 'backup' && git push
