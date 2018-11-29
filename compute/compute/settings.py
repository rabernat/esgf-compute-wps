"""
Django settings for compute project.

Generated by 'django-admin startproject' using Django 1.10.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import ConfigParser
import datetime
import kombu
import logging
import os
import netaddr

logger = logging.getLogger('settings')

class DjangoConfigParser(ConfigParser.ConfigParser):
    def __init__(self, defaults):
        self.defaults = defaults

        ConfigParser.ConfigParser.__init__(self)

    @classmethod
    def from_file(cls, file_path, defaults=None):
        config = cls(defaults or {})

        config.read([file_path])

        return config

    def get_value(self, section, key, default, value_type=str, conv=None):
        try:
            if value_type == int:
                value = self.getint(section, key)
            elif value_type == float:
                value = self.getfloat(section, key)
            elif value_type == bool:
                value = self.getboolean(section, key)
            elif value_type == list:
                value = self.get(section, key).split(',')
            else:
                value = self.get(section, key)

                for replacement in self.defaults.iteritems():
                    if replacement[0] in value:
                        value = value.replace(*replacement)
        # Error with calling NoSectionError
        except TypeError:
            value = default

            pass
        except ConfigParser.NoOptionError, ConfigParser.NoSectionError:
            value = default

            if value_type == str:
                for replacement in self.defaults.iteritems():
                    if replacement[0] in value:
                        value = value.replace(*replacement)

            pass

        if conv is not None:
            value = conv(value)

        return value

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '+a#&@l4!^)i5cn=!*ye^!42xcmyqs3l&j368ow^-y=3fs-txq6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = 'WPS_DEBUG' in os.environ
TEST = 'WPS_TEST' in os.environ

DJANGO_CONFIG_PATH = os.environ.get('DJANGO_CONFIG_PATH', '/etc/config/django.properties')

config = DjangoConfigParser.from_file(DJANGO_CONFIG_PATH)

host = config.get_value('default', 'host', '127.0.0.1')

# Celery Settings
broker_url = config.get_value('default', 'celery.broker',
                              'redis://your-boxer-redis-master:6379/0')
result_backend = config.get_value('default', 'celery.backend',
                                  'redis://your-boxer-redis-master:6379/0')

cidr = config.get_value('default', 'allowed.cidr', None, list)

# CWT WPS Settings
if cidr is not None:
    ALLOWED_HOSTS = ['*']

    if netaddr.valid_ipv4(host):
	    cidr.append(host)

    cidr = [x for x in cidr if x != '']

    ALLOWED_CIDR_NETS = cidr
else:
    ALLOWED_HOSTS = [host]

SESSION_COOKIE_NAME = config.get_value('default', 'session.cookie.name', 'wps_sessionid')

ACTIVE_USER_THRESHOLD = config.get_value('default', 'active.user.threshold', 5, int, lambda x: datetime.timedelta(days=x))
INGRESS_ENABLED = config.get_value('default', 'ingress.enabled', True, bool)
PROCESS_BLACKLIST = config.get_value('default', 'process.blacklist', [], list)
CERT_DOWNLOAD_ENABLED = config.get_value('default', 'cert.download.enabled', True, bool)
ESGF_SEARCH = config.get_value('default', 'esgf.search', 'esgf-node.llnl.gov')

WORKER_CPU_COUNT = config.get_value('default', 'worker.cpu_count', 2, int)
WORKER_CPU_UNITS = config.get_value('default', 'worker.cpu_units', 200, int)
WORKER_MEMORY = config.get_value('default', 'worker.memory', 8e6, int)
WORKER_USER_PERCENT = config.get_value('default', 'worker.user_percent', 0.10,
                                       float)
WORKER_PER_USER = ((WORKER_CPU_COUNT*1000)/WORKER_CPU_UNITS)*WORKER_USER_PERCENT


# Application definition
EMAIL_HOST = config.get_value('email', 'host', 'localhost')
EMAIL_PORT = config.get_value('email', 'port', 25, int)
EMAIL_HOST_PASSWORD = config.get_value('email', 'password', '')
EMAIL_HOST_USER = config.get_value('email', 'user', '')

METRICS_HOST = config.get_value('metrics', 'host',
                                'http://172.17.0.8:9090/prometheus/api/v1/query')

WPS_VERSION = '1.0.0'
WPS_LANG = 'en-US'
WPS_ENDPOINT = config.get_value('wps', 'wps.endpoint', 'https://{host}/wps/')
WPS_STATUS_LOCATION = config.get_value('wps', 'wps.status_location', 'https://{host}/wps/status/{job_id}/')
WPS_EXECUTE_URL = config.get_value('wps', 'wps.execute_url',
                                   'https://{host}/wps/execute/')
WPS_INGRESS_PATH = config.get_value('wps', 'wps.ingress_path', '/data/ingress')
WPS_PUBLIC_PATH = config.get_value('wps', 'wps.public_path', '/data/public')
WPS_DAP = config.get_value('wps', 'wps.dap', True, bool)
WPS_DAP_URL = config.get_value('wps', 'wps.dap_url', 'https://{host}/threddsCWT/dodsC/public/{file_name}')
WPS_LOGIN_URL = config.get_value('wps', 'wps.login_url', 'https://{host}/wps/home/auth/login/openid')
WPS_PROFILE_URL = config.get_value('wps', 'wps.profile_url', 'https://{host}/wps/home/user/profile')
WPS_OAUTH2_CALLBACK = config.get_value('wps', 'wps.oauth2.callback', 'https://{host}/auth/callback')
WPS_OPENID_TRUST_ROOT = config.get_value('wps', 'wps.openid.trust.root', 'https://{host}/')
WPS_OPENID_RETURN_TO = config.get_value('wps', 'wps.openid.return.to', 'https://{host}auth/callback/openid/')
WPS_OPENID_CALLBACK_SUCCESS = config.get_value('wps', 'wps.openid.callback.success', 'https://{host}/wps/home/auth/login/callback')
WPS_PASSWORD_RESET_URL = config.get_value('wps', 'wps.password.reset.url', 'https://{host}/wps/home/auth/reset')
WPS_CA_PATH = config.get_value('wps', 'wps.ca.path', '/tmp/certs')
WPS_LOCAL_OUTPUT_PATH = config.get_value('wps', 'wps.local.output.path', '/data/public')
WPS_USER_TEMP_PATH = config.get_value('wps', 'wps.user.temp.path', '/tmp/cwt/users')
WPS_ADMIN_EMAIL = config.get_value('wps', 'wps.admin.email', 'admin@aims2.llnl.gov')

WPS_CACHE_PATH = config.get_value('cache', 'wps.cache.path', '/data/cache')
WPS_PARTITION_SIZE = config.get_value('cache', 'wps.partition.size', 10, int)
WPS_CACHE_CHECK = config.get_value('cache', 'wps.cache.check', 1, int, lambda x: datetime.timedelta(days=x))
WPS_CACHE_GB_MAX_SIZE = config.get_value('cache', 'wps.gb.max.size', 2.097152e8, float)
WPS_CACHE_MAX_AGE = config.get_value('cache', 'wps.cache.max.age', 30, int, lambda x: datetime.timedelta(days=x))
WPS_CACHE_FREED_PERCENT = config.get_value('cache', 'wps.cache.freed.percent', 0.25, float)

WPS_CDAT_ENABLED = config.get_value('wps', 'wps.cdat.enabled', True, bool)

WPS_EDAS_ENABLED = config.get_value('edas', 'wps.edas.enabled', False, bool)
WPS_EDAS_HOST = config.get_value('edas', 'wps.edas.host', 'aims2.llnl.gov')
WPS_EDAS_REQ_PORT = config.get_value('edas', 'wps.edas.req.port', 5670, int)
WPS_EDAS_RES_PORT = config.get_value('edas', 'wps.edas.res.port', 5671, int)
WPS_EDAS_TIMEOUT = config.get_value('edas', 'wps.edas.timeout', 30, int)
WPS_EDAS_OUTPUT_PATH = config.get_value('edas', 'output.path', '/data/edask')

WPS_OPHIDIA_ENABLED = config.get_value('ophidia', 'wps.oph.enabled', False, bool)
WPS_OPHIDIA_USER = config.get_value('ophidia', 'wps.oph.user', 'oph-test')
WPS_OPHIDIA_PASSWORD = config.get_value('ophidia', 'wps.oph.password', 'abcd')
WPS_OPHIDIA_HOST = config.get_value('ophidia', 'wps.oph.host', 'aims2.llnl.gov')
WPS_OPHIDIA_PORT = config.get_value('ophidia', 'wps.oph.port', 11732, int)
WPS_OPHIDIA_OUTPUT_PATH = config.get_value('ophidia', 'wps.oph.output.path', '/wps')
WPS_OPHIDIA_OUTPUT_URL = config.get_value('ophidia', 'wps.oph.output.url', 'https://aims2.llnl.gov/thredds/dodsC{output_path}/{output_name}.nc')
WPS_OPHIDIA_DEFAULT_CORES = config.get_value('ophidia', 'wps.oph.default.cores', 8, int)

APPEND_SLASH = False

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': config.get_value('wps', 'wps.cache.path', '/tmp/django/cache'),
    }
}

INSTALLED_APPS = [
    'wps',
    'webpack_loader',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

try:
    import django_nose
except:
    pass
else:
    INSTALLED_APPS.append('django_nose')

    TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

    if DEBUG:
        NOSE_ARGS = [
            '--with-coverage',
            '--cover-package=wps.auth,wps.backend,wps.helpers,wps.tasks,wps.views',
        ]

MIDDLEWARE = [
    'allow_cidr.middleware.AllowCIDRMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'compute.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'compute.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {}

if TEST:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
else:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('POSTGRES_NAME', 'postgres'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', '1234'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
    }

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'wps', 'webapp', 'src'),
        ]
    }
]

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = '/var/www/static'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'assets'),
)

WEBPACK_LOADER = {
    'DEFAULT': {
        'BUNDLE_DIR_NAME': 'js/',
        'STATS_FILE': os.path.join(BASE_DIR, 'wps', 'webapp', 'webpack-stats.json'),
    }
}

LOGGING_BASE_PATH = '/var/log/cwt'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(levelname)s][%(asctime)s][%(filename)s[%(funcName)s:%(lineno)s]] %(message)s',
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'general': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_BASE_PATH, 'general.log'),
            'when': 'd',
            'interval': 1,
            'backupCount': 7,
        },
        'auth': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_BASE_PATH, 'auth.log'),
            'when': 'd',
            'interval': 1,
            'backupCount': 7,
        },
        'tasks': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_BASE_PATH, 'tasks.log'),
            'when': 'd',
            'interval': 1,
            'backupCount': 7,
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'general'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'wps.auth': {
            'handlers': ['auth'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'wps.views.auth': {
            'handlers': ['auth'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'wps.tasks': {
            'handlers': ['tasks'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}
