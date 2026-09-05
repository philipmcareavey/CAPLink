"""
Per-IP rate limiting (Technical Implementation Plan step 2.a.ii's other
half — see app/services/account_lockout.py for the per-account side).

Split into its own module rather than defined inline in app/main.py: the
endpoint modules that apply `@limiter.limit(...)` need to import this
object, and they're themselves imported *by* main.py (via the API
router) — importing `limiter` back from main.py would be a circular
import.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
