import logging
import signal
import sys
import time
import traceback


class Worker(object):
    """
    A generic worker class that consumes messages off of one or more
    (fixed, preferably) channels, and then dispatches them to a handler.

    Includes logic for graceful shutdown on receiving an interrupt.

    To use: Subclass, override the handle() and channel_list() methods, and
    then instantiate and call run(). Alternatively, you may pass a handler
    callable and channel list into the constructor of this base class.

    Note that channel_list is called ONCE, at the start of the run. This
    worker pattern does not support dynamic channels as that would require the
    ability to cancel an in-flight blocking listen.
    """

    def __init__(self, channel_layer, signal_handlers=True):
        self.channel_layer = channel_layer
        self.signal_handlers = signal_handlers
        self.logger = logging.getLogger('asgiref.worker')
        self.termed = False
        self.in_job = False

    def install_signal_handler(self):
        """
        Adds signal handlers to catch Ctrl-C and SIGTERM.
        """
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGINT, self.sigterm_handler)

    def sigterm_handler(self, signo, stack_frame):
        """
        Handler for signal interrupts. Immediately exits if there is not a job
        in progress, and sets a flag to exit if there is not.
        """
        self.termed = True
        if self.in_job:
            self.logger.info("Shutdown signal received while busy, waiting for loop termination")
        else:
            self.logger.info("Shutdown signal received while idle, terminating immediately")
            sys.exit(0)

    def handler(self, channel, message):
        """
        Handle a message. Override this.
        """
        raise NotImplementedError()

    def channel_list(self):
        """
        Return the list of channels to listen to (only called once). Override this.
        """
        raise NotImplementedError()

    def run(self):
        """
        Main loop/entry point
        """
        # If they requested signal handlers, install them
        if self.signal_handlers:
            self.install_signal_handler()
        # Work out what channels to listen to
        channels = self.channel_list()
        self.logger.info("Listening on channels %s", ", ".join(sorted(channels)))
        # Main loop
        while not self.termed:
            # Set the in-job flag to false only during this segment
            self.in_job = False
            channel, message = self.channel_layer.receive_many(channels, block=True)
            self.in_job = True
            # If no message, stall a little to avoid busy-looping then continue
            if channel is None:
                time.sleep(0.01)
                continue
            # Run the handler
            try:
                self.handler(channel, message)
            except:
                self.logger.exception("Error handling message: %s", traceback.format_exc())
