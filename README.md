# Isilon CloudPool Data Collector
The isi_data_collectors.py script is a script that can be used to query single cluster for and CloudPool data via the Isilon's Platform API and/or SSH. The results of those queries are processed by isi_data_collectors_process.py module. The provided module, defined in influxdb_client.py, sends query results to an InfluxDB backend. Additionally, several Grafana dashboards are provided to make it easy to monitor the health and status of your Isilon clusters.

# Installation Instructions
Those instructions assume that you have python >= 2.7, pip >=8.2.1 and git >=2.x.x installed on your VM (Ubuntu 16.04) or local system and that you have Key-based SSH access to Isilon host.


# Local Installation Instructions
The local installation simply installs the required Python dependencies on the local system. The Collector is designed to run directly from the source directory which is available from OIL bitbucket repository.
```sh
sudo git clone https://github.com/cnleng/isilon_cloudpool_collectors.git
cd isilon_cloudpool_collectors/
sudo pip install -r requirements.txt
```


# Run Instructions
* Make sure that local machine have key-based ssh  access on remote Isilon hosts (mandatory for cloudpool data).
* Install InfluxDB (version >=1.6). InfluxDB can be installed locally (i.e on the same system as the Collector) or remotely (i.e. on a different system).
```sh
sudo wget https://dl.influxdata.com/influxdb/releases/influxdb_1.6.4_amd64.deb
sudo dpkg -i influxdb_1.6.4_amd64.deb
sudo systemctl daemon-reload
sudo systemctl start influxdb
sudo systemctl status influxdb
sudo systemctl enable influxdb
```
* If you installed InfluxDB to somewhere other than localhost and/or port 8086 then you'll also need to update the configuration file with the address and port of the InfluxDB.
* Install Grafana (version 5.2.4). Grafana can be installed locally (i.e on the same system as the Collector) or remotely (i.e. on a different system).
```sh
sudo wget https://s3-us-west-2.amazonaws.com/grafana-releases/release/grafana_5.2.4_amd64.deb
sudo apt-get install -y adduser libfontconfig
sudo dpkg -i grafana_5.2.4_amd64.deb
sudo systemctl daemon-reload
sudo systemctl start grafana-server
sudo systemctl status grafana-server
sudo systemctl enable grafana-server
```
* To run the Collector:
```sh
./isi_data_collectors.py --isilon_host <isilon_host> --isilon_user <isilon_user> --isilon_passwd <isilon_password> --isilon_ssl <ssh_usage> --isilon_stats <stats_to_collect> --influx_host <influxdb_host> --influx_port <influxdb_port> --influx_user <influxdb_user> --influx_db isilon-analytic --influx_passwd <influxdb_password>
```

You can type
```sh
./isi_data_collectors.py -h
```
to get all options. Files named example-* provide examples on how to run each collection (SyncIQ, Cloudpool, file policies)


# Grafana set up
Included with the Collector source code are  Grafana dashboards that make it easy to monitor the health and status of your Isilon clusters. To view the dashboards with Grafana, follow these instructions:
* Install and configure Grafana to use the InfluxDB as a data source (You can follow the link http://docs.grafana.org/installation/). Note that the provided Grafana dashboards have been tested to work with Grafana version 5.2.4. Also, note that the influxdb_client.py creates and stores the statistic data in a database named isilon-analytics. You'll need that information when following the instructions for adding a data source to Grafana. Also, be sure to configure the isilon-analytic data source as the default Grafana data source using the Grafana Dashboard Admin web-interface.
* Once configuration is complete upload to Grafana json files located under /grafana-dashboards
