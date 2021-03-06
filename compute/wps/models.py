from __future__ import unicode_literals

import base64
import contextlib
import datetime
import hashlib
import json
import logging
import os
import random
import string
import time
from urlparse import urlparse

import cdms2
import cwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db import transaction
from django.db.models import F
from django.db.models import signals
from django.db.models.query_utils import Q
from django.utils import timezone
from openid import association
from openid.store import interface
from openid.store import nonce

from wps import helpers
from wps import metrics

logger = logging.getLogger('wps.models')

ProcessAccepted = 'ProcessAccepted'
ProcessStarted = 'ProcessStarted'
ProcessPaused = 'ProcessPaused'
ProcessSucceeded = 'ProcessSucceeded'
ProcessFailed = 'ProcessFailed'

class DjangoOpenIDStore(interface.OpenIDStore):
    # Heavily borrowed from http://bazaar.launchpad.net/~ubuntuone-pqm-team/django-openid-auth/trunk/view/head:/django_openid_auth/store.py

    def storeAssociation(self, server_url, association):
        try:
            assoc = OpenIDAssociation.objects.get(server_url=server_url,
                                                 handle=association.handle)
        except OpenIDAssociation.DoesNotExist:
            assoc = OpenIDAssociation(server_url=server_url,
                                      handle=association.handle,
                                      secret=base64.encodestring(association.secret),
                                      issued=association.issued,
                                      lifetime=association.lifetime,
                                      assoc_type=association.assoc_type)
        else:
            assoc.secret = base64.encodestring(association.secret)
            assoc.issued = association.issued
            assoc.lifetime = association.lifetime
            assoc.assoc_type = association.assoc_type

        assoc.save()

    def getAssociation(self, server_url, handle=None):
        if handle is not None:
            assocs = OpenIDAssociation.objects.filter(server_url=server_url,
                                                     handle=handle)
        else:
            assocs = OpenIDAssociation.objects.filter(server_url=server_url)

        active = []
        expired = []

        for a in assocs:
            assoc = association.Association(a.handle,
                                            base64.decodestring(a.secret.encode('utf-8')),
                                            a.issued,
                                            a.lifetime,
                                            a.assoc_type)

            expires_in = assoc.getExpiresIn()

            if expires_in == 0:
                expired.append(a)
            else:
                active.append((assoc.issued, assoc))

        for e in expired:
            e.delete()

        if len(active) == 0:
            return None

        active.sort()

        return active[-1][1]

    def removeAssociation(self, server_url, handle):
        assocs = OpenIDAssociations.objects.filter(server_url=server_url, handle=handle)

        for a in assocs:
            a.delete()

        return len(assocs) > 0

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        try:
            ononce = OpenIDNonce.objects.get(server_url__exact=server_url,
                                             timestamp__exact=timestamp,
                                             salt__exact=salt)
        except OpenIDNonce.DoesNotExist:
            ononce = OpenIDNonce.objects.create(server_url=server_url,
                                                timestamp=timestamp,
                                                salt=salt)
            return True

        return False

    def cleanupNonces(self):
        # Will implement later since it's not called
        pass

    def cleanupAssociations(self):
        # Will implement later since it's not called
        pass

class OpenIDNonce(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    server_url = models.CharField(max_length=2048)
    timestamp = models.IntegerField()
    salt = models.CharField(max_length=40)

    class Meta:
        unique_together = ('server_url', 'timestamp', 'salt')

    def __str__(self):
        return '{0.server_url}'.format(self)

class OpenIDAssociation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    server_url = models.CharField(max_length=2048)
    handle = models.CharField(max_length=256)
    secret = models.TextField(max_length=256)
    issued = models.IntegerField()
    lifetime = models.IntegerField()
    assoc_type = models.TextField(max_length=64)

    class Meta:
        unique_together = ('server_url', 'handle')

    def __str__(self):
        return ('{0.server_url} {0.handle}'.format(self))

class File(models.Model):
    name = models.CharField(max_length=256)
    host = models.CharField(max_length=256)
    variable = models.CharField(max_length=64)
    url = models.TextField()
    requested = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('name', 'host')

    @staticmethod
    def track(user, variable):
        url_parts = urlparse(variable.uri)

        parts = url_parts[2].split('/')

        file_obj, _ = File.objects.get_or_create(
            name=parts[-1],
            host=url_parts[1],
            defaults={
                'variable': variable.var_name,
                'url': variable.uri,
            }
        )

        file_obj.requested = F('requested') + 1

        file_obj.save()

        user_file_obj, _ = UserFile.objects.get_or_create(user=user, file=file_obj)

        user_file_obj.requested = F('requested') + 1

        user_file_obj.save()

    def to_json(self):
        return {
            'name': self.name,
            'host': self.host,
            'variable': self.variable,
            'url': self.url,
            'requested': self.requested
        }

    def __str__(self):
        return '{0.name}'.format(self)

class UserFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    requested_date = models.DateTimeField(auto_now=True)
    requested = models.PositiveIntegerField(default=0)

    def to_json(self):
        data = self.file.to_json()

        data['requested'] = self.requested

        data['requested_date'] = self.requested_date

        return data

    def __str__(self):
        return '{0.file.name}'.format(self)

class Cache(models.Model):
    url = models.CharField(max_length=512)
    variable = models.CharField(max_length=64)
    dimensions = models.TextField()
    added_date = models.DateTimeField(auto_now_add=True)
    accessed_date = models.DateTimeField(auto_now=True)
    size = models.BigIntegerField(blank=True)
    local_path = models.CharField(blank=True, max_length=512)

    class Meta:
        unique_together = (('url', 'variable'),)

    @contextlib.contextmanager
    def open_variable(self):
        try:
            with cdms2.open(self.local_path) as infile:
                yield infile[self.variable]
        except cdms2.CDMSError:
            raise Exception('Unabled to access cache file')

    def hash(self):
        identifier = '{!s}:{!s}'.format(self.url, self.variable)

        return hashlib.md5(identifier).hexdigest()

    def new_output_path(self):
        filename = '{!s}.nc'.format(self.hash())

        return os.path.join(settings.WPS_CACHE_PATH, filename)

    def localize_mapped(self, mapped):
        cache_mapped = helpers.decoder(self.dimensions)

        new_mapped = {}

        for key, value in cache_mapped.iteritems():
            orig = mapped[key]

            start = orig.start - value.start

            stop = start + (orig.stop - orig.start)

            new_mapped[key] = slice(start, stop, value.step)

        return new_mapped

    def check_axis(self, var, name, value):
        axis_index = var.getAxisIndex(name)

        if axis_index == -1:
            raise Exception('Axis {!r} missing from cached file'.format(name))

        axis = var.getAxis(axis_index)

        expected = value.stop - value.start

        if expected != axis.shape[0]:
            raise Exception('Axis {!r} mismatched shapes {!r}'
                            ' ({!r})'.format(name, axis.shape[0], expected))

        logger.info('Cached %r matched expected %r', value.stop-value.start,
                    expected)

    def validate(self):
        logger.info('Validating cache file %r', self.local_path)

        try:
            mapped = helpers.decoder(self.dimensions)
        except ValueError:
            raise Exception('Unabled to load dimensions')

        logger.info('Loaded dimensions %r', mapped)

        with self.open_variable() as var:
            for name, value in mapped.iteritems():
                self.check_axis(var, name, value)

    def is_superset(self, domain):
        cached = helpers.decoder(self.dimensions)

        for name, value in domain.iteritems():
            try:
                cached_value = cached[name] 
            except KeyError:
                logger.info('Missing axis %r', name)

                return False

            if (value.start < cached_value.start or
                    value.stop > cached_value.stop):
                logger.info('Axis %r not a superset, source (%r, %r), cached (%r, %r)', 
                            name, value.start, value.stop, cached_value.start, cached_value.stop)

                return False

        return True

    def accessed(self, when=None):
        if when is None:
            when = timezone.now()

        self.accessed = when

        self.save()

        logger.info('Updated accessed to %r', self.accessed)

    def set_size(self):
        stat = os.stat(self.local_path)

        self.size = stat.st_size

        self.save()

        return self.size

    def estimate_size(self):
        with cdms2.open(self.url) as infile:
            var_name, dimensions = self.dimensions.split('!')

            size = reduce(lambda x, y: x * y, infile[var_name].shape)

            size = size * infile[var_name].dtype.itemsize

        return size

    def __str__(self):
        return '{0.local_path}'.format(self)

class Auth(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    openid_url = models.CharField(max_length=256)
    type = models.CharField(max_length=64)
    cert = models.TextField()
    api_key = models.CharField(max_length=128)
    extra = models.TextField()

    def update(self, auth_type, certs, **kwargs):
        if self.api_key == '':
            self.api_key = ''.join(random.choice(string.ascii_letters+string.digits) for _ in xrange(64))

        self.type = auth_type

        self.cert = ''.join(certs)

        extra = json.loads(self.extra or '{}')

        extra.update(kwargs)

        self.extra = json.dumps(extra)

        self.save()

    def __str__(self):
        return '{0.openid_url} {0.type}'.format(self)

class Process(models.Model):
    identifier = models.CharField(max_length=128, unique=True)
    backend = models.CharField(max_length=128)
    abstract = models.TextField()
    description = models.TextField()
    enabled = models.BooleanField(default=True)

    def track(self, user):
        user_process_obj, _ = UserProcess.objects.get_or_create(user=user, process=self)

        user_process_obj.requested = F('requested') + 1

        user_process_obj.save()

    def to_json(self, usage=False):
        return {
            'identifier': self.identifier,
            'backend': self.backend,
            'enabled': self.enabled
        }

    def __str__(self):
        return '{0.identifier}'.format(self)

class UserProcess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE)
    requested_date = models.DateTimeField(auto_now=True)
    requested = models.PositiveIntegerField(default=0)

    def to_json(self):
        data = self.process.to_json()

        data['requested'] = self.requested

        data['requested_date'] = self.requested_date

        return data

    def __str__(self):
        return '{0.process.identifier}'.format(self)

class Server(models.Model):
    host = models.CharField(max_length=128, unique=True)
    added_date = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(default=1)
    capabilities = models.TextField()

    processes = models.ManyToManyField(Process)

    def __str__(self):
        return '{0.host}'.format(self)

class Job(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE, null=True)
    steps_completed = models.IntegerField(default=0)
    steps_total = models.IntegerField(default=0)
    extra = models.TextField(null=True)

    @property
    def details(self):
        return {
            'id': self.id,
            'server': self.server.host,
            'process': self.process.identifier,
            'elapsed': self.elapsed,
            #'status': self.status
        }

    @property
    def status(self):
        return [
            {
                'created_date': x.created_date,
                'updated_date': x.updated_date,
                'status': x.status,
                'exception': x.exception,
                'output': x.output,
                'messages': [y.details for y in x.message_set.all().order_by('created_date')]
            } for x in self.status_set.all().order_by('created_date')
        ]

    @property
    def elapsed(self):
        started = self.status_set.filter(status='ProcessStarted')

        ended = self.status_set.filter(Q(status='ProcessSucceeded') | Q(status='ProcessFailed'))

        if len(started) == 0 or len(ended) == 0:
            return 'No elapsed'

        elapsed = ended[0].created_date - started[0].created_date

        return '{}.{}'.format(elapsed.seconds, elapsed.microseconds)

    @property
    def report(self):
        location = settings.WPS_STATUS_LOCATION.format(job_id=self.id)

        latest = self.status_set.latest('created_date')

        if latest.exception is not None:
            ex_report = cwt.wps.CreateFromDocument(latest.exception)

            status = cwt.wps.status_failed_from_report(ex_report)
        elif latest.status == ProcessAccepted:
            status = cwt.wps.status_accepted('Job accepted')
        elif latest.status == ProcessStarted:
            message = latest.message_set.latest('created_date')

            status = cwt.wps.status_started(message.message, message.percent)
        elif latest.status == ProcessPaused:
            message = latest.message_set.latest('created_date')

            status = cwt.wps.status_paused(message.message, message.percent)
        elif latest.status == ProcessSucceeded:
            status = cwt.wps.status_succeeded('Job succeeded')

        outputs = []

        outputs.append(cwt.wps.output_data('output', 'output', latest.output))

        process = cwt.wps.process(self.process.identifier, self.process.identifier, '1.0.0')

        args = [
            process,
            status,
            '1.0.0',
            'en-US',
            settings.WPS_ENDPOINT,
            location,
            outputs
        ]

        response = cwt.wps.execute_response(*args)

        cwt.bds.reset()

        return response.toxml(bds=cwt.bds)

    @property
    def is_started(self):
        latest = self.status_set.latest('created_date')

        return latest is not None and latest.status == ProcessStarted

    @property
    def is_failed(self):
        latest = self.status_set.latest('created_date')

        return latest is not None and latest.status == ProcessFailed

    @property
    def is_succeeded(self):
        latest = self.status_set.latest('created_date')

        return latest is not None and latest.status == ProcessSucceeded

    @property
    def progress(self):
        try:
            return (self.steps_completed + 1) * 100.0 / self.steps_total
        except ZeroDivisionError:
            return 0.0

    def step_inc(self, steps=None):
        if steps is None:
            steps = 1

        self.steps_total = F('steps_total') + steps

        self.save()

        self.refresh_from_db()

    def step_complete(self):
        self.steps_completed = F('steps_completed') + 1

        self.save()

        self.refresh_from_db()

    def accepted(self):
        self.status_set.create(status=ProcessAccepted)

        metrics.WPS_JOBS_ACCEPTED.inc()

    def started(self):
        # Guard against duplicates
        if not self.is_started:
            status = self.status_set.create(status=ProcessStarted)

            status.set_message('Job Started', self.progress)

            metrics.WPS_JOBS_STARTED.inc()

    def succeeded(self, output=None):
        # Guard against duplicates
        if not self.is_succeeded:
            if output is None:
                output = ''

            status = self.status_set.create(status=ProcessSucceeded)

            status.output = output

            status.save()

            metrics.WPS_JOBS_SUCCEEDED.inc()

    def failed(self, exception):
        # Guard against duplicates
        if not self.is_failed:
            status = self.status_set.create(status=ProcessFailed)

            status.exception = exception

            status.save()

            metrics.WPS_JOBS_FAILED.inc()

    def retry(self, exception):
        self.update('Retrying... {}', exception)

    def update(self, message, *args, **kwargs):
        message = message.format(*args, **kwargs)

        started = self.status_set.filter(status=ProcessStarted).latest('created_date')

        started.set_message(message, self.progress)

    def statusSince(self, date):
        return [
            {
                'created_date': x.created_date,
                'updated_date': x.updated_date,
                'status': x.status,
                'exception': x.exception,
                'output': x.output,
                'messages': [y.details for y in x.message_set.all().order_by('created_date')]
            } for x in self.status_set.filter(updated_date__gt=date)
        ]

class Status(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=128)
    exception = models.TextField(null=True)
    output = models.TextField(null=True)

    def set_message(self, message, percent=None):
        self.message_set.create(message=message, percent=percent)

        self.updated_date = timezone.now()

        self.save()

    def __str__(self):
        return '{0.status}'.format(self)

class Message(models.Model):
    status = models.ForeignKey(Status, on_delete=models.CASCADE)

    created_date = models.DateTimeField(auto_now_add=True)
    percent = models.PositiveIntegerField(null=True)
    message = models.TextField(null=True)

    @property
    def details(self):
        return {
            'created_date': self.created_date,
            'percent': self.percent or 0,
            'message': self.message
        }

    def __str__(self):
        return '{0.message}'.format(self)
