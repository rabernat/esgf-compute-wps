#! /usr/bin/env python

import os
import re
import uuid

import cdms2
import cwt
import dask.array as da
from cdms2 import MV2 as MV
from celery.utils.log import get_task_logger

from wps import settings
from wps import WPSError
from wps.tasks import base
from wps.tasks import process
from wps.tasks import file_manager

__ALL__ = [
    'subset',
    'aggregate',
    'cache_variable'
]

logger = get_task_logger('wps.tasks.cdat')

@base.register_process('CDAT.regrid', abstract="""
Regrids a variable to designated grid. Required parameter named "gridder".
""")
@base.cwt_shared_task()
def regrid(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    def validate(op):
        op.get_parameter('gridder', True)

    return retrieve_base(self, o, None, user_id, job_id, validate) 

@base.register_process('CDAT.subset', abstract='Subset a variable by provided domain. Supports regridding.')
@base.cwt_shared_task()
def subset(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    def validate(op):
        if op.domain is None:
            raise WPSError('Missing required domain')

    return retrieve_base(self, o, None, user_id, job_id, validate) 

@base.register_process('CDAT.aggregate', abstract='Aggregate a variable over multiple files. Supports subsetting and regridding.')
@base.cwt_shared_task()
def aggregate(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    return retrieve_base(self, o, None, user_id, job_id) 

def retrieve_base(self, operation, num_inputs, user_id, job_id, validate=None):
    self.PUBLISH = base.ALL

    proc = process.Process(self.request.id)

    proc.initialize(user_id, job_id)

    proc.job.started()

    if validate is not None:
        validate(operation)

    output_name = '{}.nc'.format(str(uuid.uuid4()))

    output_path = os.path.join(settings.LOCAL_OUTPUT_PATH, output_name)

    try:
        with cdms2.open(output_path, 'w') as output_file:
            output_var_name = proc.retrieve(operation, num_inputs, output_file)
    except cdms2.CDMSError as e:
        raise base.AccessError(output_path, e.message)
    except WPSError:
        raise

    if settings.DAP:
        output_url = settings.DAP_URL.format(filename=output_name)
    else:
        output_url = settings.OUTPUT_URL.format(filename=output_name)

    output_variable = cwt.Variable(output_url, output_var_name).parameterize()

    return {operation.name: output_variable}

#@base.register_process('CDAT.max', abstract=""" 
#Computes the maximum over an axis. Requires singular parameter named "axes" 
#whose value will be used to process over. The value should be a "|" delimited
#string e.g. 'lat|lon'.
#""")
#@base.cwt_shared_task()
#def maximum(self, parent_variables, variables, domains, operation, user_id, job_id):
#    return process_base(self, MV.max, 1, parent_variables, variables, domains, operation, user_id, job_id)

@base.register_process('CDAT.average', abstract=""" 
Computes the average over an axis. Requires singular parameter named "axes" 
whose value will be used to process over. The value should be a "|" delimited
string e.g. 'lat|lon'.
""")
@base.cwt_shared_task()
def average(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    return process_base(self, MV.average, 1, o, user_id, job_id)

@base.register_process('CDAT.sum', abstract=""" 
Computes the sum over an axis. Requires singular parameter named "axes" 
whose value will be used to process over. The value should be a "|" delimited
string e.g. 'lat|lon'.
""")
@base.cwt_shared_task()
def sum(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    return process_base(self, MV.sum, 1, o, user_id, job_id)

@base.register_process('CDAT.max', abstract=""" 
Computes the maximum over an axis. Requires singular parameter named "axes" 
whose value will be used to process over. The value should be a "|" delimited
string e.g. 'lat|lon'.
""")
@base.cwt_shared_task()
def maximum(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    return process_base(self, MV.max, 1, o, user_id, job_id)

@base.register_process('CDAT.min', abstract="""
Computes the minimum over an axis. Requires singular parameter named "axes" 
whose value will be used to process over. The value should be a "|" delimited
string e.g. 'lat|lon'.
                       """)
@base.cwt_shared_task()
def minimum(self, parent_variables, variables, domains, operation, user_id, job_id):
    _, _, o = self.load(parent_variables, variables, domains, operation)

    return process_base(self, MV.min, 1, o, user_id, job_id)

def process_base(self, process_func, num_inputs, operation, user_id, job_id):
    self.PUBLISH = base.ALL

    proc = process.Process(self.request.id)

    proc.initialize(user_id, job_id)

    proc.job.started()

    output_name = '{}.nc'.format(str(uuid.uuid4()))

    output_path = os.path.join(settings.LOCAL_OUTPUT_PATH, output_name)

    try:
        with cdms2.open(output_path, 'w') as output_file:
            output_var_name = proc.process(operation, num_inputs, output_file, process_func)
    except cdms2.CDMSError as e:
        logger.exception('CDMS ERROR')
        raise base.AccessError(output_path, e)
    except WPSError:
        logger.exception('WPS ERROR')
        raise

    if settings.DAP:
        output_url = settings.DAP_URL.format(filename=output_name)
    else:
        output_url = settings.OUTPUT_URL.format(filename=output_name)

    output_variable = cwt.Variable(output_url, output_var_name).parameterize()

    return {operation.name: output_variable}

@base.cwt_shared_task()
def cache_variable(self, parent_variables, variables, domains, operation, user_id, job_id):
    self.PUBLISH = base.RETRY | base.FAILURE

    _, _, o = self.load(parent_variables, variables, domains, operation)

    proc = process.Process(self.request.id)

    proc.initialize(user_id, job_id)

    proc.job.started()

    output_name = '{}.nc'.format(str(uuid.uuid4()))

    output_path = os.path.join(settings.LOCAL_OUTPUT_PATH, output_name)

    try:
        with cdms2.open(output_path, 'w') as output_file:
            output_var_name = proc.retrieve(o, None, output_file)
    except cdms2.CDMSError as e:
        raise base.AccessError(output_path, e.message)
    except WPSError:
        raise

    if settings.DAP:
        output_url = settings.DAP_URL.format(filename=output_name)
    else:
        output_url = settings.OUTPUT_URL.format(filename=output_name)

    output_variable = cwt.Variable(output_url, output_var_name).parameterize()

    return {o.name: output_variable}
