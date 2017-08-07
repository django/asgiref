class TypeDispatchConsumer(object):
    """
    Consumer which dispatches to other consumers based on the type of incoming
    connection.

    Provide the type consumers as body attributes, like:
        http = MyHttpConsumer

    Or as constructor arguments, like:
        TypeDispatchConsumer(http=MyHttpConsumer)
    """

    def __init__(self, **kwargs):
        # Set any passed consumers onto our instance
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __call__(self, type, reply, channel_layer, consumer_channel):
        # See if there's something that can handle this on us
        consumer = getattr(self, type, None)
        if consumer and callable(consumer):
            return consumer(
                type=type,
                reply=reply,
                channel_layer=channel_layer,
                consumer_channel=consumer_channel,
            )
        else:
            raise ValueError("No consumer configured for type %r" % type)
