from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBServerError, InfluxDBClientError

import getpass
import logging
import time
import requests.exceptions
import sys

LOG = logging.getLogger(__name__)

class InfluxdbDAO(object):
        def __init__(self, host, port, db, username, password):
            self._host = host
            self._port = port
            self._db = db
            self._username = username
            self._password = password

        def save(self, points):
            global g_client
            g_client = InfluxDBClient(host=self._host, port=self._port, database=self._db,username=self._username, password=self._password)

            create_database = True
            try:
                databases = g_client.get_list_database()
            except (requests.exceptions.ConnectionError, InfluxDBClientError) as exc:
                msg = "Failed to connect to InfluxDB server at %s:%s "\
                            "database: %s.\nERROR: %s" % (influxdb_host, str(influxdb_port), influxdb_name, str(exc))
                print >> sys.stderr, msg
                LOG.error(msg)
                sys.exit(1)

            for database in databases:
                if database["name"] == self._db:
                    create_database = False
                    break

            if create_database is True:
                LOG.info("Creating database: %s.", self._db)
                g_client.create_database(self._db)

            g_client.write_points( points, time_precision='ms')

        def delete(self, measurement=None, tags=None):
            global g_client
            g_client = InfluxDBClient(host=self._host, port=self._port, database=self._db,username=self._username, password=self._password)

            try:
                g_client.delete_series(measurement=measurement, tags=tags)
            except (requests.exceptions.ConnectionError, InfluxDBClientError) as exc:
                msg = "Failed to deltete series to InfluxDB server at %s:%s "\
                            "database: %s.\nERROR: %s" % (influxdb_host, str(influxdb_port), influxdb_name, str(exc))
                print >> sys.stderr, msg
                LOG.debug(msg)
                sys.exit(1)
