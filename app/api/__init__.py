"""
ERE PDF Pipeline API

FastAPI-based REST API for document processing.
"""

from .ere_api import create_app, EREPipelineAPI

__all__ = ["create_app", "EREPipelineAPI"]
