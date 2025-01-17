#!/usr/bin/env python
# Check that we can fetch attachments for 99.9% of our syncing accounts.
from __future__ import print_function

from gevent import monkey

monkey.patch_all()

import datetime
from collections import defaultdict

import click
from gevent.pool import Pool
from sqlalchemy import true
from sqlalchemy.sql.expression import func

from inbox.crispin import connection_pool
from inbox.error_handling import maybe_enable_rollbar
from inbox.logging import configure_logging, get_logger
from inbox.models import Account, Block
from inbox.models.backends.generic import GenericAccount
from inbox.models.session import (
    global_session_scope,
    session_scope,
    session_scope_by_shard_id,
)
from inbox.s3.base import get_raw_from_provider
from inbox.s3.exc import EmailFetchException, TemporaryEmailFetchException

configure_logging()
log = get_logger(purpose="separator-backfix")

NUM_MESSAGES = 10


def process_account(account_id):
    ret = defaultdict(int)

    try:
        with session_scope(account_id) as db_session:
            acc = db_session.query(Account).get(account_id)
            db_session.expunge(acc)

        one_month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        for _ in range(NUM_MESSAGES):
            with session_scope(account_id) as db_session:
                block = (
                    db_session.query(Block)
                    .filter(
                        Block.namespace_id == acc.namespace.id,
                        Block.created_at < one_month_ago,
                    )
                    .order_by(func.rand())
                    .limit(1)
                    .first()
                )

                if block is None:
                    continue

                if len(block.parts) == 0:
                    ret["null_failures"] += 1
                    continue

                message = block.parts[0].message
                raw_mime = get_raw_from_provider(message)

            if raw_mime != "":
                ret["successes"] += 1
            else:
                ret["null_failures"] += 1
    except Exception as e:
        ret[type(e).__name__] += 1

    return ret


@click.command()
@click.option("--num-accounts", type=int, default=1500)
def main(num_accounts):
    maybe_enable_rollbar()

    with global_session_scope() as db_session:
        accounts = (
            db_session.query(Account)
            .filter(Account.sync_should_run == true())
            .order_by(func.rand())
            .limit(num_accounts)
            .all()
        )

        accounts = [acc.id for acc in accounts][:num_accounts]
        db_session.expunge_all()

    pool = Pool(size=100)
    results = pool.map(process_account, accounts)

    global_results = dict()
    for ret in results:
        for key in ret:
            if key not in global_results:
                global_results[key] = 0

            global_results[key] += ret[key]

    print(global_results)


if __name__ == "__main__":
    main()
