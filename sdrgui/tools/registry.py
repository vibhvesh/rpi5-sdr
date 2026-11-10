"""Discover built-in tools. New tools: add sdrgui/tools/<name>/ with a Tool subclass."""
from .classifier import ClassifierTool
from .direction_finder import DirectionFinderTool
from .scanner import ScannerTool
from .iq_recorder import IqRecorderTool

_TOOLS = None

def all_tool_classes():
    return [ClassifierTool, DirectionFinderTool, ScannerTool, IqRecorderTool]

def load_tools():
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = [cls() for cls in all_tool_classes()]
    return _TOOLS

def get_tool(name):
    for t in load_tools():
        if t.name == name:
            return t
    return None

def enabled_tools(cfg):
    return [t for t in load_tools() if t.is_enabled(cfg)]

def all_tools():
    return load_tools()
