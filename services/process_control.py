#!/usr/bin/env python3
"""Compatibility alias for the single bounded subprocess implementation."""
from command import run, kill_group as stop_group

def install_signal_handlers():
    return None
