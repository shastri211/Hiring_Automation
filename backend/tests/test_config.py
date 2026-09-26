from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_ipv6_hosts_are_bracketed_in_connection_urls():
    s = Settings(POSTGRES_SERVER="::1", REDIS_HOST="::1", POSTGRES_PORT="5432")
    url = make_url(s.SQLALCHEMY_DATABASE_URI)
    assert (url.host, url.port) == ("::1", 5432)
    assert s.REDIS_URL.startswith("redis://[::1]:")


def test_hostnames_and_ipv4_are_unchanged():
    s = Settings(POSTGRES_SERVER="127.0.0.1", REDIS_HOST="redis")
    assert "@127.0.0.1:" in s.SQLALCHEMY_DATABASE_URI
    assert s.REDIS_URL.startswith("redis://redis:")
