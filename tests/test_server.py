from asgiref.server import StatelessServer


def test_stateless_server():
    """StatelessServer can be instantiated with an ASGI 3 application."""

    async def app(scope, receive, send):
        pass

    server = StatelessServer(app)
    server.get_or_create_application_instance("scope_id", {})
