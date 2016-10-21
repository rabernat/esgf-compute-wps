import os
import uuid

from pywps import config
from wps.processes import data_manager
from wps.processes import esgf_operation

class EchoOperation(esgf_operation.ESGFOperation):
    def __init__(self):
        super(EchoOperation, self).__init__()

    @property
    def title(self):
        return 'Test Echo'

    def __call__(self, operation, auth, status):
        dm = data_manager.DataManager()

        output_path = config.getConfigValue('server', 'outputPath', '/var/wps')

        output_name = '%s.json' % (str(uuid.uuid4()),)

        output_file = os.path.join(output_path, output_name)

        dm.write(output_file, operation.parameterize())

        self.set_output(output_file, '')
