#! /usr/bin/env python

import cdms2
import cwt
import hashlib
import json
from celery.utils.log import get_task_logger

from wps import models
from wps import settings
from wps.tasks import base

__ALL__ = [
    'DataSet',
    'FileManager',
]

logger = get_task_logger('wps.tasks.file_manager')

class DataSet(object):
    def __init__(self, file_obj, url, variable_name):
        self.file_obj = file_obj

        self.cache_obj = None

        self.cache = None

        self.url = url

        self.variable_name = variable_name

        self.temporal_axis = None

        self.spatial_axis = {}

        self.temporal = None

        self.spatial = {}

    @property
    def shape(self):
        if self.file_obj is not None:
            return self.file_obj[self.variable_name].shape

        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def partitions(self, axis_name):
        axis = None

        if (self.temporal_axis is not None and 
                self.temporal_axis.id == axis_name):
            axis = self.temporal_axis
        elif (axis_name in self.spatial_axis):
            axis = self.spatial_axis[axis_name]
        else:
            axis_index = self.file_obj[self.variable_name].getAxisIndex(axis_name)

            if axis_index == -1:
                raise base.WPSError('Could not find axis "{name}"', name=axis_name)

            axis = self.file_obj[self.variable_name].getAxis(axis_index)

        if axis.isTime():
            if isinstance(self.temporal, slice):
                start = self.temporal.start

                stop = self.temporal.stop
            elif isinstance(self.temporal, (list, tuple)):
                indices = self.get_time().mapInterval(self.temporal)

                start = indices[0]

                stop = indices[1]
            else:
                raise base.WPSError('Temporal domain has unknown type "{name}"', name=type(self.temporal))

            diff = stop - start

            step = min(diff, settings.PARTITION_SIZE)

            for begin in xrange(start, stop, step):
                end = min(begin + step, stop)

                yield slice(begin, end), self.spatial
        else:
            pass

    def check_cache(self):
        uid = '{}:{}'.format(self.url, self.variable_name)

        uid_hash = hashlib.sha256(uid).hexdigest()

        logger.info('Checking for dataset "{}" in cache'.format(uid_hash))

        index_domain = {
            'temporal': None,
            'spatial': {}
        }

        if isinstance(self.temporal, (list, tuple)):
            indices = self.get_time().mapInterval(self.temporal)

            index_domain['temporal'] = slice(indices[0], indices[1])
        else:
            index_domain['temporal'] = self.temporal

        for name in self.spatial.keys():
            if isinstance(self.spatial[name], (list, tuple)):
                indices = self.get_axis(name).mapInterval(self.spatial[name])

                index_domain['spatial'][name] = slice(indices[0], indices[1])
            else:
                index_domain['spatial'][name] = self.spatial[name]

        logger.info('Index domain {}'.format(index_domain))

        cache_entries = models.Cache.objects.filter(uid=uid_hash)

        logger.info('Found "{}" cache entries matching hash "{}"'.format(len(cache_entries), uid_hash))

        for entry in cache_entries:
            if entry.is_superset(index_domain):
                logger.info('Found a superset')

                self.cache = entry

                break

        cache_file_path = '{}/{}.nc'.format(settings.CACHE_PATH, uid_hash)

        if self.cache is None:
            logger.info('Creating cache file for "{}"'.format(self.url))

            try:
                self.cache_obj = cdms2.open(cache_file_path, 'w')
            except cdms2.CDMSError as e:
                logger.exception('Error creating cache file "{}": {}'.format(cache_file_path, e.message))

                pass
            else:
                dimensions = json.dumps(index_domain, default=models.slice_default)

                self.cache = models.Cache.objects.create(uid=uid_hash, url=self.url, dimensions=dimensions)

                logger.info('Creating cache entry for "{}"'.format(self.url))
        else:
            logger.info('Using cache file "{}" as input'.format(cache_file_path))

            try:
                cache_obj = cdms2.open(cache_file_path)
            except cdms2.CDMSError as e:
                logger.exception('Error opening cached file "{}": {}'.format(cache_file_path, e.message))
                # Might need to adjust the existing cache entry or remove
                pass
            else:
                self.close()

                self.file_obj = cache_obj

                logger.info('Swapped source for cached file')

    def str_to_int(self, value):
        try:
            return int(value)
        except ValueError:
            raise base.WPSError('Could not convert "{value}" to int', value=value)

    def str_to_int_float(self, value):
        try:
            return self.str_to_int(value)
        except base.WPSError:
            pass

        try:
            return float(value)
        except ValueError:
            raise base.WPSError('Could not convert "{value}" to float or int', value=value)

    def dimension_to_cdms2_selector(self, dimension):
        if dimension.crs == cwt.VALUES:
            start = self.str_to_int_float(dimension.start)

            end = self.str_to_int_float(dimension.end)

            selector = (start, end)
        elif dimension.crs == cwt.INDICES:
            start = self.str_to_int(dimension.start)

            end = self.str_to_int(dimension.end)

            step = self.str_to_int(dimension.step)

            selector = slice(start, end, step)
        else:
            raise base.WPSError('Error handling CRS "{name}"', name=dimension.crs)

        return selector

    def map_domain(self, domain):
        variable = self.file_obj[self.variable_name]

        for dim in domain.dimensions:
            axis_index = variable.getAxisIndex(dim.name)

            if axis_index == -1:
                raise base.WPSError('Dimension "{name}" was not found in "{url}"', name=dim.name, url=self.url)

            axis = variable.getAxis(axis_index)

            if axis.isTime():
                self.temporal = self.dimension_to_cdms2_selector(dim)
            else:
                self.spatial[dim.name] = self.dimension_to_cdms2_selector(dim)

    def get_time(self):
        if self.temporal_axis is None:
            try:
                self.temporal_axis = self.file_obj[self.variable_name].getTime()
            except cdms2.CDMSError as e:
                raise base.AccessError(self.url, e.message)

        return self.temporal_axis

    def get_axis(self, name):
        if name not in self.spatial_axis:
            axis_index = self.file_obj[self.variable_name].getAxisIndex(name)

            if axis_index == -1:
                raise WPSError('Axis "{name}" does not exist', name=name)

            self.spatial_axis[name] = self.file_obj[self.variable_name].getAxis(axis_index)

        return self.spatial_axis[name]

    def close(self):
        if self.temporal_axis is not None:
            self.temporal_axis = None

        self.spatial_axis = {}
        
        if self.file_obj is not None:
            self.file_obj.close()

            self.file_obj = None

    def __del__(self):
        self.close()

    def __repr__(self):
        return 'DataSet(url={url}, variable_name={variable_name}, temporal_roi={temporal}, spatial_roi={spatial})'.format(
                url=self.url,
                variable_name=self.variable_name,
                temporal=self.temporal,
                spatial=self.spatial
            )

class FileManager(object):
    def __init__(self, variables):
        self.variables = variables

        self.datasets = []

    def __enter__(self):
        try:
            for var in self.variables:
                file_obj = cdms2.open(var.uri)

                self.datasets.append(DataSet(file_obj, var.uri, var.var_name))
        except cdms2.CDMSError as e:
            self.close()

            raise base.AccessError(var.uri, e.message)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def sorted(self, limit=None):
        self.datasets = sorted(self.datasets, key=lambda x: x.get_time().units)

        if limit is not None:
            for x in xrange(limit, len(self.datasets)):
                self.datasets[x].close()

            self.datasets = self.datasets[:limit]

        for ds in self.datasets:
            yield ds

    def close(self):
        for ds in self.datasets:
            ds.close()

        self.datasets = []

    def __del__(self):
        self.close()
