#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Python Serverless Function Entrypoint
Routes /api/* and fallback requests through DotaAnalystHandler from server.py
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import DotaAnalystHandler


class handler(DotaAnalystHandler):
    pass
