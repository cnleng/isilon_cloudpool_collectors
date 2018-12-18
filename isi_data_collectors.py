#!/usr/bin/env python

import sys

from isi_data_collectors_config import parse_cli, \
        configure_logging_via_cli, configure_process
from isi_data_collectors_process import IsiDataCollectorsProcess


def main():
    args = parse_cli()
    # validate the pid_file arg and get the full path to it.
    daemon = IsiDataCollectorsProcess()

    if args.isilon_host is None  \
            or args.isilon_user is None  \
            or args.isilon_passwd is None  \
            or args.isilon_stats is None  \
            or args.influx_host is None  \
            or args.influx_db is None:
        print >> sys.stderr, "Invalid arguments, Check usage : python isi_data_collectors.py -h"
        sys.exit(1)
    else:
        configure_logging_via_cli(args)
        configure_process(daemon, args)
        daemon.start()

if __name__ == "__main__":
    main()
