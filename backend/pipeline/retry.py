"""Small retry helper with exponential backoff + jitter."""
import time
import random
import logging

log = logging.getLogger("pipeline.retry")


def with_retries(fn, *, attempts=4, base_delay=2.0, max_delay=30.0, retry_on=(Exception,), label="op"):
    """Call fn() with retries. Raises the last exception if all attempts fail.

    base_delay grows exponentially (base, base*2, base*4, ...) capped at max_delay,
    with jitter to avoid thundering-herd against rate-limited APIs.
    """
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except retry_on as exc:  # noqa: BLE001 - intentional broad catch, configurable
            last_exc = exc
            if i == attempts - 1:
                break
            delay = min(base_delay * (2 ** i), max_delay)
            delay += random.uniform(0, delay * 0.25)
            log.warning("%s failed (attempt %d/%d): %s -- retrying in %.1fs",
                        label, i + 1, attempts, exc, delay)
            time.sleep(delay)
    raise last_exc
