#!/usr/bin/env python

from __future__ import print_function

import click

from inbox.error_handling import maybe_enable_rollbar
from inbox.models.account import Account
from inbox.models.session import global_session_scope


@click.command()
@click.argument("account_id")
@click.option("--desired-host")
@click.option("--dry-run", is_flag=True)
@click.option("--toggle-sync", is_flag=True)
def main(account_id, desired_host, dry_run, toggle_sync):
    maybe_enable_rollbar()

    with global_session_scope() as db_session:
        account = db_session.query(Account).get(int(account_id))

        print("Before sync host: {}".format(account.sync_host))
        print("Before desired sync host: {}".format(account.desired_sync_host))
        print("Before sync should run: {}".format(account.sync_should_run))

        if dry_run:
            return
        account.desired_sync_host = desired_host
        if toggle_sync:
            account.sync_should_run = not account.sync_should_run

        print("After sync host: {}".format(account.sync_host))
        print("After desired sync host: {}".format(account.desired_sync_host))
        print("After sync should run: {}".format(account.sync_should_run))
        db_session.commit()


if __name__ == "__main__":
    main()
