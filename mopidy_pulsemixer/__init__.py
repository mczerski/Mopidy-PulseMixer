from __future__ import unicode_literals

import os

from mopidy import config, ext


__version__ = '0.1.0'


class Extension(ext.Extension):

    dist_name = 'Mopidy-PulseMixer'
    ext_name = 'pulsemixer'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['sink'] = config.String()
        schema['min_volume'] = config.Integer(minimum=0, maximum=100)
        schema['max_volume'] = config.Integer(minimum=0, maximum=100)
        schema['volume_scale'] = config.String(
            choices=('linear', 'cubic', 'log'))
        return schema

    def setup(self, registry):
        from mopidy_pulsemixer.mixer import PulseMixer

        registry.add('mixer', PulseMixer)
