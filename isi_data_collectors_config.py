"""
This file contains utility functions for configuring the IsiDataInsightsDaemon
via command line args and config file.
"""
import argparse
import ConfigParser
import getpass
import logging
import os
import re
import sys
import urllib3

from ast import literal_eval

from isi_stats_api_client import IsiStatsApiClient
from influxdb_client import InfluxdbDAO

LOG = logging.getLogger(__name__)
DEFAULT_LOG_FILE = "./isi_data_collectors.log"
DEFAULT_LOG_LEVEL = "INFO"
STATS_NAME = {'sync_iq':'sync_iq_stats', 'cloud_pool':'cloud_pool_stats', 'file_pool':'file_pool_stats'}

def _log_level_str_to_enum(log_level):
    if log_level.upper() == "DEBUG":
        return logging.DEBUG
    elif log_level.upper() == "INFO":
        return logging.INFO
    elif log_level.upper() == "WARNING":
        return logging.WARNING
    elif log_level.upper() == "ERROR":
        return logging.ERROR
    elif log_level.upper() == "CRITICAL":
        return logging.CRITICAL
    else:
        print "Invalid logging level: " + log_level + ", setting to INFO."
        return logging.INFO

def _print_stat_groups(daemon):
    """
    Print out the list of stat sets that were configured for the daemon prior
    to starting it so that user can verify that it was configured as expected.
    """
    for update_interval, stat_set in daemon.get_next_stat_set():
        msg = "Configured stat set:\n\tClusters: %s\n\t"\
                "Update Interval: %d\n\tStat Keys: %s" \
                % (str(stat_set.cluster_configs), update_interval,
                        str(stat_set.stats))
        # print it to stdout and the log file.
        print msg
        LOG.debug(msg)

def parse_cli():
    """
    Setup the command line args and parse them.
    """
    argparser = argparse.ArgumentParser(description='Starts Isilon Data Collector Process.')
    argparser._action_groups.pop()
    required = argparser.add_argument_group('Required arguments')
    optional = argparser.add_argument_group('Optional arguments')
    required.add_argument('--isilon_host', help="Specifies Isilon host ip")
    required.add_argument('--isilon_user', help="Specifies Isilon username")
    required.add_argument('--isilon_passwd', help="Specifies Isilon user password")
    #optional.add_argument('--config', help="Specifies All configurations", nargs='?', const='config.json', default='config.json')
    optional.add_argument('--isilon_ssl', help="Specifies whether SSL verification should be done on Isilon host. Default value is n ", nargs='?', const='n', default='n')
    required.add_argument('--isilon_stats', help="Specifies Statistics to retrieve from Isilon host. valid values are {0}".format(STATS_NAME.keys()) )

    required.add_argument('--influx_host', help="Specifies InfluxDB host ip. Default value is localhost.", nargs='?', const='localhost', default='localhost')
    optional.add_argument('--influx_port', help="Specifies InfluxDB port. Default value is 8086.", nargs='?', const='8086', default='8086')
    required.add_argument('--influx_db', help="Specifies InfluxDB database to use. If it does no exsist, it will be created.")
    optional.add_argument('--influx_user', help="Set the path to the daemon pid file. The default value is root.")
    optional.add_argument('--influx_passwd', help="Set the path to the daemon pid file. The default value is root.")

    optional.add_argument('--log_file', help="Set the path to the log file. The default value is %s" % DEFAULT_LOG_FILE, nargs='?', const=DEFAULT_LOG_FILE, default=DEFAULT_LOG_FILE)
    optional.add_argument('--log_level', help="Set the log level. The default value is INFO", nargs='?', const='INFO', default=DEFAULT_LOG_LEVEL)

    return argparser.parse_args()

def configure_process(daemon, args):
    """
    Configure the daemon's stat groups and the stats processor via command line
    arguments.
    """
    _configure_stat_client(daemon, args)
    _configure_stat_dao(daemon, args)
    _configure_stat_name(daemon, args)
    #_print_stat_groups(daemon)

def _configure_stat_client(daemon, args):
    """
    Configure the daemon's stat isilon client
    """
    username = args.isilon_user
    password = args.isilon_passwd
    host = args.isilon_host
    if args.isilon_ssl is None:
        verify_ssl = False
    elif args.isilon_ssl == 'y':
        verify_ssl = True
    else:
        verify_ssl = False
    isi_api_client = IsiStatsApiClient(host, username, password, verify_ssl)
    daemon.set_stat_client(isi_api_client)
    LOG.info("Collecting data from Isilon host %s " % args.isilon_host)

def _configure_stat_dao(daemon, args):
    """
    Configure the daemon's stat DAO
    """
    username = args.influx_user
    password = args.influx_passwd
    host = args.influx_host
    db = args.influx_db
    port = args.influx_port
    influx_dao = InfluxdbDAO(host, port, db, username, password)
    daemon.set_stat_dao(influx_dao)
    LOG.info("Pushing data collection %s to InfluxDB host %s " % (args.isilon_stats, args.influx_host) )

def _configure_stat_name(daemon, args):
    """
    Configure the daemon's stat name
    """
    if args.isilon_stats is None:
        print >> sys.stderr, "You must provide stats to query via the --isilon_stats command line argument."
        sys.exit(1)
    try:
        stat_name = STATS_NAME[args.isilon_stats]
    except KeyError:
        print >> sys.stderr, "You must provide valid stats to query via the --isilon_stats command line argument. Availables values are {0}".format(STATS_NAME.keys())
        sys.exit(1)
    if stat_name is None:
        print >> sys.stderr, "You must provide valid stats to query via the --isilon_stats command line argument. Availables values are {0}".format(STATS_NAME.keys())
        sys.exit(1)
    daemon.set_stat_name(stat_name)

def configure_logging_via_cli(args):
    """
    Setup the logging from command line args.
    """
    if args.log_file is None:
        args.log_file = DEFAULT_LOG_FILE

    parent_dir = os.path.dirname(args.log_file)
    if parent_dir and os.path.exists(parent_dir) is False:
        print >> sys.stderr, "Invalid log file path: %s." % (args.log_file)
        sys.exit(1)

    if args.log_level is None:
        args.log_level = DEFAULT_LOG_LEVEL

    log_level = _log_level_str_to_enum(args.log_level)
    logging.basicConfig(filename=args.log_file, level=log_level, format='%(asctime)s:%(name)s:%(levelname)s: %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s: %(message)s')
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)
    LOG.info("Logging Data collectors in file %s" % args.log_file)

def read_config(options):
    """
    reading configuration file
    """
    configuration = dict()
