import logging
import urllib3
import requests
import json
import time
import ast
import paramiko
import sys
import isi_sdk_8_1_1
from isi_sdk_8_1_1.rest import ApiException


LOG = logging.getLogger(__name__)
# When getting metadata for multiple stats, if there are less than
# MAX_DIRECT_METADATA_STATS then do the query as multiple direct key queries,
# otherwise do it as a single batch query and filter the results on the client
# side. Testing revealed that 200 is the optimal cutoff point for a virtual
# cluster.
MAX_RESULTS = 100000
FILE_ENCODING = 'iso-8859-15'
CLOUD_POOL_FILE_SIZE_END_POINT = '/cloud/job-file/size/'


class IsiStatsApiClient(object):
    """
    Handles the details of querying for Isilon cluster statistics values and
    metadata using the Isilon SDK.
    """
    def __init__(self, host, username, password, verify_ssl=False):
        """
        Setup the Isilon SDK to query the specified cluster's statistics.
        :param StatisticsApi stats_api: instance of StatisticsApi from the
        isi_sdk_8_1_1 or isi_sdk_7_2 package.
        """
        # get the Statistics API
        self._host = host
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl


    def query_sync_iq_stats(self):
        """
        Query SyncIQ jobs data
        start_time The time the job started in unix epoch seconds.
        end_time The time the job ended in unix epoch seconds.
        network_bytes_to_source The total number of bytes sent to the source by this job.
        network_bytes_to_target The total number of bytes sent to the target by this job.
        """
        # Configure HTTP basic authorization: basicAuth
        configuration = isi_sdk_8_1_1.Configuration()
        configuration.host = 'https://' + self._host + ':8080'
        configuration.username = self._username
        configuration.password = self._password
        configuration.verify_ssl = self._verify_ssl

        if self._verify_ssl is False:
            urllib3.disable_warnings()

        # create an instance of the API class
        api_instance = isi_sdk_8_1_1.SyncApi(isi_sdk_8_1_1.ApiClient(configuration))
        resume = ""
        sync_reports = []
        collection_time = int(round(time.time() * 1000))
        LOG.info("Collecting SyncIQ data from Isilon host [%s] " % self._host)
        #print >> sys.stdout, "Collecting SyncIQ data from Isilon host [%s] " % self._host
        while (resume != None):
            if resume != "":
                api_response = api_instance.get_sync_reports(resume=resume,limit=MAX_RESULTS)
            else:
                api_response = api_instance.get_sync_reports(limit=MAX_RESULTS)
            resume = api_response.resume
            sync_reports.extend([{'host':self._host, 'collection_time':collection_time, 'sync_job_id':r.id, 'policy_id':r.policy_id,'total_data_bytes':r.total_data_bytes,'job_id':r.job_id, 'duration':r.duration, 'start_time':r.start_time, 'end_time':r.end_time, 'state':r.state,'data_replicated':r.network_bytes_to_source, 'data_to_be_replicated':r.network_bytes_to_target} for r in api_response.reports])

        return sync_reports


    def query_cloudpool_stats(self):
        """
        Query cloudpool data
        """
        # Configure HTTP basic authorization: basicAuth
        configuration = isi_sdk_8_1_1.Configuration()
        configuration.host = 'https://' + self._host + ':8080'
        configuration.username = self._username
        configuration.password = self._password
        configuration.verify_ssl = self._verify_ssl

        if self._verify_ssl is False:
            urllib3.disable_warnings()

        # create an instance of the API class
        api_instance = isi_sdk_8_1_1.CloudApi(isi_sdk_8_1_1.ApiClient(configuration))
        resume = ""
        cloud_jobs = []

        # Get all cloud jobs
        while (resume != None):
            if resume != "":
                api_response = api_instance.list_cloud_jobs(resume=resume,limit=MAX_RESULTS)
            else:
                api_response = api_instance.list_cloud_jobs(limit=MAX_RESULTS)
            resume = api_response.resume

            cloud_jobs.extend([{'cloud_job_id':r.id,'host':self._host,'create_time':r.create_time, \
            'effective_state':r.effective_state,'cloud_job_type':r.type, 'completion_time':r.completion_time, \
            'files_total':r.files.total, 'files_total_canceled':r.files.total_canceled, 'files_total_failed':r.files.total_failed, \
            'files_total_pending':r.files.total_pending, 'files_total_processing':r.files.total_processing, 'files_total_succeeded':r.files.total_succeeded} for r in api_response.jobs])

        # For each jobs with files total != 0, fetch Cloud Job Files
        # cloud_job_id -> {cloud_job_files, create_time, effective_state, cloud_job_type, files_total}
        cloud_jobs_files = []
        # Get all cloud job files
        for cloud_job in cloud_jobs:
            resume = ""
            files = {}
            LOG.info("Collecting cloudpool data from Isilon host [%s] and Job with id [%s]" % (self._host,str(cloud_job['cloud_job_id'])))
            #print >> sys.stdout, "Collecting cloudpool data from Isilon host [%s] and Job with id [%s]" % (self._host,str(cloud_job['cloud_job_id']))
            if cloud_job['files_total'] != 0:
                while (resume != None):
                    if resume != "":
                        api_response = api_instance.get_cloud_jobs_file(str(cloud_job['cloud_job_id']),resume=resume,limit=MAX_RESULTS, batch='true')
                    else:
                        api_response = api_instance.get_cloud_jobs_file(str(cloud_job['cloud_job_id']),limit=MAX_RESULTS, batch='true')
                    resume = api_response.resume

                    for f in api_response.files:
                        if ast.literal_eval(f)['name'].encode(FILE_ENCODING)!='<missing>':
                            files[ast.literal_eval(f)['name'].encode(FILE_ENCODING)] = ast.literal_eval(f)['state']

                    #files.extend(['name':ast.literal_eval(f)['name'].encode(FILE_ENCODING) for f in api_response.files if ast.literal_eval(f)['name'].encode(FILE_ENCODING)!='<missing>'])
                # For each cloud job map entry -> request to FlasK REST service to get File size
                #response = requests.post('http://' + self._host + CLOUD_POOL_FILE_SIZE_END_POINT, data={'files':files})
                if len(files) != 0:
                    # Using ssh access on Clusters
                    file_with_sizes = []
                    LOG.info("Collecting cloudpool data from Isilon host [%s] and Job with id [%s] and files %s" % (self._host,str(cloud_job['cloud_job_id']), str(files.keys())))
                    file_with_sizes = self._remote_file_size(self._host, self._username, self._password, files.keys())
                    cloud_file_size = 0
                    for f in file_with_sizes:
                        cloud_job_file = dict()
                        cloud_job_file['host'] = cloud_job['host']
                        cloud_job_file['cloud_job_id'] = cloud_job['cloud_job_id']
                        cloud_job_file['cloud_job_type'] = cloud_job['cloud_job_type']
                        cloud_job_file['effective_state'] = cloud_job['effective_state']
                        cloud_job_file['create_time'] = cloud_job['create_time']
                        cloud_job_file['file_name'] = f['name']
                        cloud_job_file['file_state'] = files[f['name']]
                        cloud_job_file['file_sizes'] = f['size']
                        cloud_file_size = cloud_file_size + int(f['size'])
                        if cloud_job['completion_time'] is None:
                            cloud_job['completion_time'] = None
                            cloud_job_file['completion_time'] = None
                        else:
                            cloud_job_file['completion_time'] = cloud_job['completion_time']
                        cloud_jobs_files.append(cloud_job_file)
                    cloud_job['file_size'] = cloud_file_size
                else:
                    cloud_job_file = dict()
                    cloud_job_file['host'] = cloud_job['host']
                    cloud_job_file['cloud_job_id'] = cloud_job['cloud_job_id']
                    cloud_job_file['cloud_job_type'] = cloud_job['cloud_job_type']
                    cloud_job_file['effective_state'] = cloud_job['effective_state']
                    cloud_job_file['create_time'] = cloud_job['create_time']
                    cloud_job_file['file_name'] = 'No files tiered'
                    cloud_job_file['file_state'] = None
                    cloud_job_file['file_sizes'] = 0
                    if cloud_job['completion_time'] is None:
                        cloud_job['completion_time'] = None
                        cloud_job_file['completion_time'] = None
                    else:
                        cloud_job_file['completion_time'] = cloud_job['completion_time']
                    cloud_jobs_files.append(cloud_job_file)
                    cloud_job['file_size'] = 0
            else:
                cloud_job_file = dict()
                cloud_job_file['host'] = cloud_job['host']
                cloud_job_file['cloud_job_id'] = cloud_job['cloud_job_id']
                cloud_job_file['cloud_job_type'] = cloud_job['cloud_job_type']
                cloud_job_file['effective_state'] = cloud_job['effective_state']
                cloud_job_file['create_time'] = cloud_job['create_time']
                cloud_job_file['file_name'] = 'No files tiered'
                cloud_job_file['file_state'] = None
                cloud_job_file['file_sizes'] = 0
                if cloud_job['completion_time'] is None:
                    cloud_job['completion_time'] = None
                    cloud_job_file['completion_time'] = None
                else:
                    cloud_job_file['completion_time'] = cloud_job['completion_time']
                cloud_jobs_files.append(cloud_job_file)
                cloud_job['file_size'] = 0

        return cloud_jobs_files, cloud_jobs

    def query_file_pool_stats(self):
        """
        Query filepool data
        """
        # Configure HTTP basic authorization: basicAuth
        configuration = isi_sdk_8_1_1.Configuration()
        configuration.host = 'https://' + self._host + ':8080'
        configuration.username = self._username
        configuration.password = self._password
        configuration.verify_ssl = self._verify_ssl

        if self._verify_ssl is False:
            urllib3.disable_warnings()

        file_pools = []
        resume = ""
        # create an instance of the API class
        api_instance = isi_sdk_8_1_1.FilepoolApi(isi_sdk_8_1_1.ApiClient(configuration))
        api_response = api_instance.list_filepool_policies()

        file_pools.extend([{'host':self._host,'apply_order':r.apply_order, \
        'birth_cluster_id':r.birth_cluster_id,'description':r.description, 'name':r.name, \
        'id':r.id, 'state':r.state, \
        'state_details':r.state_details} for r in api_response.policies])
        return file_pools

    def _remote_file_size(self, host, username, password, file_paths):
            """
            Get size of files located on a remote server
            """

            results = []
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                #ssh.connect( host, username=username, password=password, timeout=5)
                ssh.connect( host, timeout=5)
                sftp = ssh.open_sftp()

                for file_path in file_paths:
                    file_size = 0
                    try:
                        info = sftp.stat(file_path)
                        file_size = info.st_size
                    except Exception as ex:
                        LOG.debug("An error occured while getting file size for [%s], %s" % (file_path,ex))
                    results.append({'name':file_path,'size':file_size})
            except Exception as e:
                LOG.error("An error occured while connecting via SSH to Isilon cluster [%s], [%s], " % (self._host,e))
                sys.exit(1)
            finally:
                if ssh:
                    ssh.close()

            return results
