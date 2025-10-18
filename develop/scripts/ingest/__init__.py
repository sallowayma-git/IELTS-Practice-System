"""HTML转JSON脚本的核心包。"""

from . import datamodel as _datamodel
from .datamodel import *  # noqa: F401,F403 - 暴露数据模型供外部直接使用

__all__ = _datamodel.__all__
