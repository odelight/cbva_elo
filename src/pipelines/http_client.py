"""Rate-limited HTTP client for CBVA scraping."""

import requests
import time
import threading

# Default timeout for HTTP requests (connect timeout, read timeout)
DEFAULT_TIMEOUT = (10, 30)
# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # Exponential backoff multiplier


class RateLimitedClient:
    """HTTP client that enforces a minimum interval between requests."""

    def __init__(self, requests_per_second=None):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()

    def get(self, url, **kwargs):
        """Make a GET request, respecting rate limits with retries."""
        if self.requests_per_second:
            with self.lock:
                now = time.time()
                min_interval = 1.0 / self.requests_per_second
                elapsed = now - self.last_request_time
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                self.last_request_time = time.time()

        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = DEFAULT_TIMEOUT

        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return requests.get(url, **kwargs)
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF ** attempt
                    time.sleep(wait_time)

        raise last_exception


# Global client instance
_client = RateLimitedClient()


def configure_rate_limit(requests_per_second):
    """Configure the global rate limit for all HTTP requests."""
    global _client
    _client = RateLimitedClient(requests_per_second)


def get(url, **kwargs):
    """Make a rate-limited GET request."""
    return _client.get(url, **kwargs)
