"""Resources of the Data Market API, one class per group of endpoints.

Each resource method builds an ``Operation`` and hands it to the client's
transport, so the synchronous and asynchronous clients share every decision
except the I/O call.
"""

from __future__ import annotations
