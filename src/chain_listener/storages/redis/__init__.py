"""Redis storage backend package.

Importing from this submodule requires the optional aioredis dependency.
"""

from .redis import RedisStorage

__all__ = ["RedisStorage"]

