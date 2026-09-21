"""Run the installed Agent Control AF_UNIX projection receiver."""
import signal
from threading import Event

from django.core.management.base import BaseCommand, CommandError

from backend.api.event_delivery import TrustedDjangoProjectionReceiver


class Command(BaseCommand):
    help = "Run the trusted Agent Control domain-event projection receiver."

    def handle(self, *args, **options):
        stop = Event()
        receiver = None

        def request_stop(signum, frame):
            stop.set()

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        try:
            receiver = TrustedDjangoProjectionReceiver.from_installed_config()
            receiver.bind()
            receiver.serve_forever(stop)
        except Exception as error:
            raise CommandError("Trusted projection receiver unavailable.") from error
        finally:
            if receiver is not None:
                receiver.close()
