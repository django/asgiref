import asyncio
import socket as sock

import pytest
import pytest_asyncio

from asgiref.server import StatelessServer


async def sock_recvfrom(sock, n):
    while True:
        try:
            return sock.recvfrom(n)
        except BlockingIOError:
            await asyncio.sleep(0)


class Server(StatelessServer):
    def __init__(self, application, max_applications=1000):
        super().__init__(
            application,
            max_applications=max_applications,
        )
        self._sock = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind(("127.0.0.1", 0))

    @property
    def address(self):
        return self._sock.getsockname()

    async def handle(self):
        while True:
            data, addr = await sock_recvfrom(self._sock, 4096)
            data = data.decode("utf-8")

            if data.startswith("Register"):
                _, usr_name = data.split(" ")
                input_quene = self.get_or_create_application_instance(usr_name, addr)
                input_quene.put_nowait(b"Welcome")

            elif data.startswith("To"):
                _, usr_name, msg = data.split(" ", 2)
                input_quene = self.get_or_create_application_instance(usr_name, addr)
                input_quene.put_nowait(msg.encode("utf-8"))

    async def application_send(self, scope, message):
        self._sock.sendto(message, scope)

    def close(self):
        self._sock.close()
        for details in self.application_instances.values():
            details["future"].cancel()


class Client:
    def __init__(self, name):
        self._sock = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        self._sock.setblocking(False)
        self.name = name

    async def register(self, server_addr, name=None):
        name = name or self.name
        self._sock.sendto(f"Register {name}".encode(), server_addr)

    async def send(self, server_addr, to, msg):
        self._sock.sendto(f"To {to} {msg}".encode(), server_addr)

    async def get_msg(self):
        msg, server_addr = await sock_recvfrom(self._sock, 4096)
        return msg, server_addr

    def close(self):
        self._sock.close()


@pytest_asyncio.fixture(scope="function")
async def server():
    async def app(scope, receive, send):
        while True:
            msg = await receive()
            await send(msg)

    server = Server(app, 10)
    yield server
    server.close()


async def check_client_msg(client, expected_address, expected_msg):
    msg, server_addr = await asyncio.wait_for(client.get_msg(), timeout=1.0)
    assert msg == expected_msg
    assert server_addr == expected_address


@pytest.mark.asyncio
async def test_stateless_server(server):
    """StatelessServer can be instantiated with an ASGI 3 application."""
    """Create a UDP Server can register instance based on name from message of client.
    Clients can communicate to other client by name through server"""

    client1 = Client(name="client1")
    client2 = Client(name="client2")

    async def check_client1_behavior():
        await client1.register(server.address)
        await check_client_msg(client1, server.address, b"Welcome")
        await client1.send(server.address, "client2", "Hello")

    async def check_client2_behavior():
        await client2.register(server.address)
        await check_client_msg(client2, server.address, b"Welcome")
        await check_client_msg(client2, server.address, b"Hello")

    class Done(Exception):
        pass

    async def do_test():
        await asyncio.gather(check_client1_behavior(), check_client2_behavior())
        raise Done

    try:
        await asyncio.gather(server.arun(), do_test())
    except Done:
        pass


@pytest.mark.asyncio
async def test_server_delete_instance(server):
    """The max_applications of Server is 10. After 20 times register, application number should be 10."""
    client1 = Client(name="client1")

    class Done(Exception):
        pass

    async def client1_multiple_register():
        for i in range(20):
            await client1.register(server.address, name=f"client{i}")
            print(f"client{i}")
            await check_client_msg(client1, server.address, b"Welcome")
        raise Done

    try:
        await asyncio.gather(client1_multiple_register(), server.arun())
    except Done:
        pass
