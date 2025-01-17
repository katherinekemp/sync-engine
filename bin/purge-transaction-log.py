#!/usr/bin/env python
"""
Deletes entries in the transaction older than `days_ago` days( as measured by
the created_at column)

"""
from __future__ import absolute_import, print_function

from gevent import monkey

monkey.patch_all()

import logging
import sys

import click
import gevent

from inbox.config import config
from inbox.error_handling import maybe_enable_rollbar
from inbox.logging import configure_logging, get_logger
from inbox.models.util import purge_transactions

configure_logging(logging.INFO)
log = get_logger()


@click.command()
@click.option("--days-ago", type=int, default=60)
@click.option("--limit", type=int, default=1000)
@click.option("--throttle", is_flag=True)
@click.option("--dry-run", is_flag=True)
def run(days_ago, limit, throttle, dry_run):
    maybe_enable_rollbar()

    print("Python", sys.version, file=sys.stderr)

    pool = []

    for host in config["DATABASE_HOSTS"]:
        pool.append(
            gevent.spawn(
                purge_old_transactions, host, days_ago, limit, throttle, dry_run
            )
        )

    gevent.joinall(pool)


def purge_old_transactions(host, days_ago, limit, throttle, dry_run):
    while True:
        for shard in host["SHARDS"]:
            # Ensure shard is explicitly not marked as disabled
            if "DISABLED" in shard and not shard["DISABLED"]:
                log.info(
                    "Spawning transaction purge process for shard", shard_id=shard["ID"]
                )
                purge_transactions(shard["ID"], days_ago, limit, throttle, dry_run)
            else:
                log.info(
                    "Will not spawn process for disabled shard", shard_id=shard["ID"]
                )
        gevent.sleep(600)


if __name__ == "__main__":
    run()
