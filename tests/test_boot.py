import random
import os

import unittest

from boot import CredentialsGetter, connect_to_network


class MockCredentialsFile:

    _ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, contents):
        self.contents = contents
        self.filename = "".join(random.choice(self._ascii_letters) for _ in range(10)) + ".txt"

    def __enter__(self):
        with open(self.filename, 'w') as f:
            f.write(self.contents)
            f.flush()
        return self.filename

    def __exit__(self, exc_type, exc_value, traceback):
        os.remove(self.filename)


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


class BootTest(unittest.TestCase):

    def setUp(self):
        self.fake_network = FakeNetworkInterface()
        self.fake_credentials = FakeCredentialsGetter()

    def test_get_credentials(self):
        file_contents = "test_ssid\ntest_password"
        with MockCredentialsFile(file_contents) as cred_file:
            getter = CredentialsGetter(cred_file)
            ssid, password = getter.get_credentials()
        assert ssid == "test_ssid"
        assert password == "test_password"


    def test_connect_to_network_raises_runtime_error_on_failed_connection(self):
        fake_network = FakeNetworkInterface(resolved_status_code=1)
        fake_credentials = FakeCredentialsGetter()

        with self.assertRaises(RuntimeError):
            connect_to_network(fake_network, fake_credentials, fake_sleep)

    def test_connect_to_network_returns_ip_address_on_success(self):
        fake_network = FakeNetworkInterface(resolved_ip_address='192.168.0.2')
        fake_credentials = FakeCredentialsGetter()
        ip_address = connect_to_network(fake_network, fake_credentials, fake_sleep)
        assert ip_address == '192.168.0.2'


if __name__ == "__main__":
    unittest.main()
