#!/usr/bin/env python

from __future__ import print_function

from sys import exit

import click

from inbox.config import config
from inbox.error_handling import maybe_enable_rollbar
from inbox.heartbeat.status import clear_heartbeat_status
from inbox.logging import configure_logging, get_logger

configure_logging(config.get("LOGLEVEL"))
log = get_logger()


@click.command()
@click.option("--host", "-h", type=str)
@click.option("--port", "-p", type=int, default=6379)
@click.option("--account-id", "-a", type=int, required=True)
@click.option("--folder-id", "-f", type=int)
@click.option("--device-id", "-d", type=int)
def main(host, port, account_id, folder_id, device_id):
    maybe_enable_rollbar()

    print("Clearing heartbeat status...")
    n = clear_heartbeat_status(account_id, folder_id, device_id, host, port)
    print("{} folders cleared.".format(n))
    exit(0)


if __name__ == "__main__":
    main()
