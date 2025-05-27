import tempfile
from contextlib import contextmanager

import pytest

from boot import CredentialsGetter, connect_to_network


@contextmanager
def credentials_file(contents):
    """Context manager to create a temporary credentials file."""
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
        f.write(contents)
        f.flush()
        yield f.name


def test_get_credentials():
    file_contents = "test_ssid\ntest_password"
    with credentials_file(file_contents) as cred_file:
        getter = CredentialsGetter(cred_file)
        ssid, password = getter.get_credentials()
        assert ssid == "test_ssid"
        assert password == "test_password"


class FakeNetworkInterface:
    """A mock network interface for testing purposes."""
    def __init__(self, resolved_ip_address='192.168.0.1', resolved_status_code=3):
        self.status_code = 0
        self.resolved_status_code = resolved_status_code
        self.resolved_ip_address = resolved_ip_address

    def active(self, state):
        pass

    def connect(self, ssid, password):
        self.status_code = self.resolved_status_code

    def status(self):
        return self.status_code

    def ifconfig(self):
        return (self.resolved_ip_address,)


def fake_sleep(seconds):
    """A fake sleep function that does nothing."""
    pass


class FakeCredentialsGetter:
    """A mock credentials getter for testing purposes."""
    def get_credentials(self):
        return "test_ssid", "test_password"


def test_connect_to_network_raises_runtime_error_on_failed_connection():
    fake_network = FakeNetworkInterface(resolved_status_code=1)
    fake_credentials = FakeCredentialsGetter()

    with pytest.raises(RuntimeError, match='Failed to establish a network connection'):
        connect_to_network(fake_network, fake_credentials, fake_sleep)


def test_connect_to_network_returns_ip_address_on_success():
    fake_network = FakeNetworkInterface(resolved_ip_address='192.168.0.2')
    fake_credentials = FakeCredentialsGetter()
    ip_address = connect_to_network(fake_network, fake_credentials, fake_sleep)
    assert ip_address == '192.168.0.2'



