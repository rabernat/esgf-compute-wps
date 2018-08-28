#! /usr/bin/env python

import collections
import datetime
import hashlib
import json
import re

import cdms2
import cdtime
import requests
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from . import common
from wps import WPSError
from wps import tasks
from wps import helpers

logger = common.logger

def describe_axis(axis):
    """ Describe an axis.
    Args:
        axis: A cdms2.axis.TransientAxis or cdms2.axis.FileAxis.

    Returns:
        A dict describing the axis.
    """
    return {
        'id': axis.id,
        'start': float(axis[0]),
        'stop': float(axis[-1]),
        'units': axis.units or None,
        'length': len(axis),
    }

def process_axes(header):
    """ Processes the axes of a file.
    Args:
        header: A cdms2.fvariable.FileVariable.

    Returns:
        A dict containing the url, temporal and spatial axes.
    """
    data = {}
    base_units = None

    for axis in header.getAxisList():
        logger.info('Processing axis %r', axis.id)

        if axis.isTime():
            if base_units is None:
                base_units = axis.units

            axis_clone = axis.clone()

            axis_clone.toRelativeTime(base_units)

            data['temporal'] = describe_axis(axis_clone)
        else:
            desc = describe_axis(axis)

            if 'spatial' not in data:
                data['spatial'] = [desc]
            else:
                data['spatial'].append(desc)

    return data

def process_url(prefix_id, url, variable):
    """ Processes a url.
    Args:
        prefix_id: A str prefix to build the cache id.
        url: A str url path.
        variable: A str variable name.

    Returns:
        A list of dicts describing each files axes.
    """
    cache_id = '{}|{}'.format(prefix_id, url)

    cache_id = hashlib.md5(cache_id).hexdigest()

    data = cache.get(cache_id)

    logger.info('Processing %r in %r', variable, url)

    if data is None:
        data = { 'url': url }

        with cdms2.open(url) as infile:
            axes = process_axes(infile[variable])

        data.update(axes)

        cache.set(cache_id, data, 24*60*60)

    return data

def retrieve_axes(user, dataset_id, variable, urls):
    """ Retrieves the axes for a set of urls.
    Args:
        user: A wps.models.User object.
        dataset_id: A str dataset id.
        variable: A str variable name.
        urls: A list of str url paths.
        
    Returns:
        A list of dicts containing the axes of each file.
    """
    prefix_id = '{}|{}'.format(dataset_id, variable)

    axes = []

    tasks.load_certificate(user)

    for url in sorted(urls):
        data = process_url(prefix_id, url, variable)

        axes.append(data)

    return axes

def search_params(dataset_id, query, shard):
    """ Prepares search params for ESGF.
    Args:
        dataset_id: A str dataset id.
        query: A str search query.
        shard: A str shard to search.

    Returns:
        A dict containing the search params.
    """
    params = {
        'type': 'File',
        'dataset_id': dataset_id,
        'format': 'application/solr+json',
        'offset': 0,
        'limit': 10000,
    }

    if query is not None and len(query.strip()) > 0:
        params['query'] = query.strip()

    if shard is not None and len(shard.strip()) > 0:
        params['shards'] = '{}/solr'.format(shard.strip())

    # enabled distrib search by default
    params['distrib'] = 'true'

    logger.info('ESGF search params %r', params)

    return params

def parse_solr_docs(response):
    """ Parses the solr response docs.
    Args:
        response: A str response from a solr search in json format.

    Returns:
        A dict containing the parsed variables and files.

        {
            "variables": {
                "tas": [0,2,3,4]
            },
            "files": [
                'file1.nc',
                'file2.nc',
                ...
                'file20.nc',
            ]
        }
    """
    variables = {}
    files = []

    for doc in response['response']['docs']:
        variable = doc['variable']

        try:
            open_dap = [x for x in doc['url'] if 'opendap' in x.lower()][0]
        except IndexError:
            logger.warning('Skipping %r, missing OpenDAP url', doc['master_id'])

            continue

        url, _, _ = open_dap.split('|')

        url = url.replace('.html', '')

        if url not in files:
            files.append(url)

        for x, var in enumerate(variable):
            if var not in variables:
                variables[var] = []

            index = files.index(url)

            # Collect the indexes of the files containing this variable
            variables[var].append(index)

    return { 'variables': variables, 'files': files }


def search_solr(dataset_id, index_node, shard=None, query=None):
    """ Search ESGF solr.
    Args:
        dataset_id: A str dataset id.
        index_node: A str of the host to run the search on.
        shard: A str shard name to pass.
        query: A str query to pass.

    Returns:
        A dict containing the parsed solr documents.
    """
    data = cache.get(dataset_id)

    if data is None:
        params = search_params(dataset_id, query, shard)

        url = 'http://{}/esg-search/search'.format(index_node)

        logger.info('Searching %r', url)

        try:
            response = requests.get(url, params)
        except requests.ConnectionError:
            raise Exception('Connection timed out')
        except requests.RequestException as e:
            raise Exception('Request failed: "{}"'.format(e))

        try:
            response_json = json.loads(response.content)
        except:
            raise Exception('Failed to load JSON response')

        data = parse_solr_docs(response_json)

        cache.set(dataset_id, data, 24*60*60)

    return data

@require_http_methods(['GET'])
@ensure_csrf_cookie
def search_variable(request):
    try:
        common.authentication_required(request)

        try:
            dataset_id = request.GET['dataset_id']

            index_node = request.GET['index_node']

            variable = request.GET['variable']

            files = request.GET['files']
        except KeyError as e:
            raise common.MissingParameterError(name=e.message)

        files = json.loads(files)
        
        if not isinstance(files, list):
            files = [files]

        shard = request.GET.get('shard', None)

        query = request.GET.get('query', None)

        dataset_variables = search_solr(dataset_id, index_node, shard, query)

        urls = [dataset_variables['files'][int(x)] for x in files]

        axes = retrieve_axes(request.user, dataset_id, variable, urls)
    except WPSError as e:
        logger.exception('Error retrieving ESGF search results')

        return common.failed(e.message)
    else:
        return common.success(axes)

@require_http_methods(['GET'])
@ensure_csrf_cookie
def search_dataset(request):
    try:
        common.authentication_required(request)

        try:
            dataset_id = request.GET['dataset_id']

            index_node = request.GET['index_node']
        except KeyError as e:
            raise common.MissingParameterError(name=e.message)

        shard = request.GET.get('shard', None)

        query = request.GET.get('query', None)

        dataset_variables = search_solr(dataset_id, index_node, shard, query)
    except WPSError as e:
        logger.exception('Error retrieving ESGF search results')

        return common.failed(e.message)
    else:
        return common.success(dataset_variables)
