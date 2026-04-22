"""Block-paged KV cache for Apple unified memory.

Adapted from the vLLM PagedAttention design (arXiv:2309.06180). The public
surface is :class:`PagedKVCacheManager`; :class:`PagedCacheConfig` carries
the shape parameters. :class:`PrefixCache` adds content-addressed block
reuse across sequences on top.
"""

from __future__ import annotations

from vmlx.cache.paged import PagedCacheConfig, PagedKVCacheManager
from vmlx.cache.prefix import PrefixCache, PrefixCacheStats

__all__ = [
    "PagedCacheConfig",
    "PagedKVCacheManager",
    "PrefixCache",
    "PrefixCacheStats",
]
