
from daemons.prefab import run
from ast import literal_eval
import logging
import sys
import time
import urllib3.exceptions

LOG = logging.getLogger(__name__)

class IsiDataCollectorsProcess():
    """
    Periodically query a list of OneFS clusters for statistics and
    process them via a configurable stats processor module.
    """
    def __init__(self):
        """
        Initialize.
        """
        self._isi_api_client = None
        self._influx_dao = None
        self._stat_name = None

    def start(self):
        """
        Start collecting data
        """
        points = []
        MB_UNIT = 0.000001
        if self._stat_name == 'sync_iq_stats':
            results = self._isi_api_client.query_sync_iq_stats()
            for r in results:
                start_time = 0
                end_time = 0
                throughput = 0.0
                duration = 0
                # set up
                if r['start_time'] is None:
                    start_time = 0
                else:
                    start_time = int(r['start_time'])
                # set up
                if r['end_time'] is None:
                    end_time = 0
                else:
                    end_time = int(r['end_time'])
                # set up
                if r['duration'] is None:
                    duration = 0
                else:
                    duration = int(r['duration'])

                # compute throughput
                data_amount = int(r['total_data_bytes'])
                if data_amount == 0:
                    throughput = 0.0
                elif duration == 0:
                    throughput = 0.0
                else:
                    throughput = data_amount*MB_UNIT / duration*1.0
                point = {'measurement':self._stat_name, 'tags':{'host':r['host'], 'sync_job_id':r['sync_job_id'], 'job_state':r['state'], 'policy_id':r['policy_id']}, \
                                        'fields': {'collection_time':r['collection_time'], 'job_id':r['job_id'], \
                                        'start_time':start_time*1000, 'end_time':end_time*1000, 'duration':duration,'state':r['state'], \
                                        'total_data_bytes':int(r['total_data_bytes'])*MB_UNIT,'data_replicated':int(r['data_replicated'])*MB_UNIT, 'data_to_be_replicated':int(r['data_to_be_replicated'])*MB_UNIT, 'throughput':throughput} }
                self._influx_dao.delete(measurement=self._stat_name, tags={'host':str(r['host']), 'sync_job_id':str(r['sync_job_id'])})
                points.append(point)
            self._influx_dao.save(points)
        if self._stat_name == 'file_pool_stats':
            file_pool_points = []
            file_pool_results = self._isi_api_client.query_file_pool_stats()
            for r in file_pool_results:
                point = {'measurement':self._stat_name, 'tags':{'host':r['host'],'policy_id':r['id']}, \
                'fields': {'apply_order':r['apply_order'], 'birth_cluster_id':r['birth_cluster_id'], \
                'description':r['description'], 'name':r['name'], 'policy_state':r['state'],\
                'state_details':r['state_details']}}
                self._influx_dao.delete(measurement=self._stat_name, tags={'host':str(r['host']),'policy_id':str(r['id'])})
                file_pool_points.append(point)
            self._influx_dao.save(file_pool_points)
        if self._stat_name == 'cloud_pool_stats':
            points_files = []
            cloud_job_files_results, cloud_job_results = self._isi_api_client.query_cloudpool_stats()

            for r in cloud_job_files_results:
                self._influx_dao.delete(measurement=self._stat_name+'_details', tags={'host':str(r['host']), 'cloud_job_id':str(r['cloud_job_id'])})
            for r in cloud_job_files_results:
                create_time = 0
                completion_time = 0
                throughput = 0.0
                duration = 0
                # set up
                if r['create_time'] is None:
                    create_time = 0
                else:
                    create_time = int(r['create_time'])
                # set up
                if r['completion_time'] is None:
                    completion_time = None
                else:
                    completion_time = int(r['completion_time'])
                point = {'measurement':self._stat_name+'_details', 'tags':{'host':r['host'], 'cloud_job_id':r['cloud_job_id'], 'file_name':r['file_name'].encode('utf-8'), 'cloud_job_type':r['cloud_job_type'], 'job_state':r['effective_state']}, \
                                        'fields': {'effective_state':r['effective_state'], \
                                        'create_time':create_time*1000, 'completion_time':None if completion_time is None else completion_time*1000, \
                                        'file_name':r['file_name'].encode('utf-8'), 'file_state':r['file_state'], 'file_size':int(r['file_sizes'])*MB_UNIT, 'throughput':throughput} }

                points_files.append(point)
            self._influx_dao.save(points_files)
            points_jobs = []
            for r in cloud_job_results:
                create_time = 0
                completion_time = 0
                throughput = 0.0
                duration = 0
                # set up
                if r['create_time'] is None:
                    create_time = 0
                else:
                    create_time = int(r['create_time'])
                # set up
                if r['completion_time'] is None:
                    completion_time = None
                else:
                    completion_time = int(r['completion_time'])
                # compute throughput
                if completion_time is None:
                    throughput = 0.0
                else:
                    throughput = int(r['file_size'])*MB_UNIT / (completion_time - create_time)*1.0

                point = {'measurement':self._stat_name, 'tags':{'host':r['host'], 'cloud_job_id':r['cloud_job_id'], 'cloud_job_type':r['cloud_job_type'], 'job_state':r['effective_state']}, \
                                        'fields': {'effective_state':r['effective_state'], \
                                        'create_time':create_time*1000, 'completion_time':None if completion_time is None else completion_time*1000, 'files_total':r['files_total'], \
                                        'files_total_canceled':r['files_total_canceled'], 'files_total_failed':r['files_total_failed'], \
                                        'files_total_pending':r['files_total_pending'], 'files_total_processing':r['files_total_processing'], \
                                        'files_total_succeeded':r['files_total_succeeded'], 'file_size':int(r['file_size'])*MB_UNIT, 'throughput':throughput} }
                self._influx_dao.delete(measurement=self._stat_name, tags={'host':str(r['host']),'cloud_job_id':str(r['cloud_job_id'])})
                points_jobs.append(point)
            self._influx_dao.save(points_jobs)

    def set_stat_client(self, api_client):
        """
        Set isilon api client
        """
        self._isi_api_client = api_client

    def set_stat_dao(self, dao):
        """
        Set dao, influxdb in this case
        """
        self._influx_dao = dao

    def set_stat_name(self, stat):
        """
        Set stat name to collect
        """
        self._stat_name = stat
