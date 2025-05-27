class AbsractCredentialsGetter:

    def get_credentials(self) -> tuple[str, str]:
        raise NotImplementedError("This method should be overridden by subclasses")


class CredentialsGetter(AbsractCredentialsGetter):

    def __init__(self, filename: str):
        self.filename = filename

    def get_credentials(self) -> tuple[str, str]:
        try:
            with open(self.filename, 'r') as f:
                ssid, password = f.read().strip().split('\n')
                return ssid, password
        except FileNotFoundError:
            raise RuntimeError('Credentials file not found. Please create credentials.txt with SSID and password.')


def connect_to_network(network_interface, credentials_getter: AbsractCredentialsGetter, wait_seconds):
    """
    Use provided credentials getter to connect to the network.
    """
    ssid, password = credentials_getter.get_credentials()

    network_interface.active(True)
    network_interface.connect(ssid, password)

    # Wait for Wi-Fi connection
    connection_timeout = 10
    while connection_timeout > 0:
        if network_interface.status() >= 3:
            break
        connection_timeout -= 1
        wait_seconds(1)

    # Check if connection is successful
    if network_interface.status() != 3:
        raise RuntimeError('Failed to establish a network connection')
    else:
        network_info = network_interface.ifconfig()
        return network_info[0]


def _wait_for_network(seconds):
    print('-> waiting for network...')
    sleep(seconds)


if __name__ == '__main__':
    print("Running boot.py...")

    from time import sleep
    from network import WLAN, STA_IF

    wlan = WLAN(STA_IF)
    credentials_getter = CredentialsGetter('credentials.txt')
    ip_address = connect_to_network(wlan, credentials_getter, _wait_for_network)
    print('-> network connection established!')
    print('-> IP address:', ip_address)



