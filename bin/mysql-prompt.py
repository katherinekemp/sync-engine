#!/usr/bin/env python
from __future__ import print_function

import subprocess
import sys

import click

from inbox.config import config
from inbox.error_handling import maybe_enable_rollbar


@click.command()
@click.option("--shard-num", type=int)
def main(shard_num):
    maybe_enable_rollbar()

    users = config.get_required("DATABASE_USERS")

    creds = dict(hostname=None, username=None, password=None, db_name=None)

    for database in config.get_required("DATABASE_HOSTS"):
        for shard in database["SHARDS"]:
            if shard["ID"] == shard_num:
                creds["hostname"] = database["HOSTNAME"]
                hostname = creds["hostname"]
                creds["username"] = users[hostname]["USER"]
                creds["password"] = users[hostname]["PASSWORD"]
                creds["db_name"] = shard["SCHEMA_NAME"]
                break

    for key in creds.keys():
        if creds[key] is None:
            print("Error: {key} is None".format(key=key))
            sys.exit(-1)

    proc = subprocess.Popen(
        [
            "mysql",
            "-h" + creds["hostname"],
            "-u" + creds["username"],
            "-D " + creds["db_name"],
            "-p" + creds["password"],
            "--safe-updates",
        ]
    )
    proc.wait()


if __name__ == "__main__":
    main()
