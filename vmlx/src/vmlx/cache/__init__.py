"""Block-paged KV cache for Apple unified memory.

Adapted from the vLLM PagedAttention design (arXiv:2309.06180). The public
surface is :class:`PagedKVCacheManager`; :class:`PagedCacheConfig` carries
the shape parameters.
"""

from __future__ import annotations

from vmlx.cache.paged import PagedCacheConfig, PagedKVCacheManager

__all__ = ["PagedCacheConfig", "PagedKVCacheManager"]
