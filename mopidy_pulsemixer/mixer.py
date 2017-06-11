from __future__ import unicode_literals

import logging
import math
import select
import threading

import pulsectl

from gi.repository import GstAudio

from mopidy import exceptions, mixer

import pykka


logger = logging.getLogger(__name__)


class PulseMixer(pykka.ThreadingActor, mixer.Mixer):

    name = 'pulsemixer'

    def __init__(self, config):
        super(PulseMixer, self).__init__()
        self.config = config
        self.sink_name = self.config['pulsemixer']['sink']
        self.min_volume = self.config['pulsemixer']['min_volume']
        self.max_volume = self.config['pulsemixer']['max_volume']
        self.volume_scale = self.config['pulsemixer']['volume_scale']
        self.pulse = pulsectl.Pulse('PulseMixer')
        self.sink = None
        sinks = self.pulse.sink_list()
        for sink in sinks:
            if sink.name == self.sink_name:
                self.sink = sink
                break
        if self.sink is None:
            raise exceptions.MixerError(
                'Could not find Pulseaudio sink %(sink)s. '
                'Available sinks include: %(sinks)s' % {
                    'sink': self.sink_name,
                    'sinks': ', '.join([sink.name for sink in sinks]),
                })
        self._last_volume = None
        self._last_mute = None
        logger.info(
            'Mixing using Pulseaudio, source "%s".',
            self.sink_name)

    def on_start(self):
        self._observer = PulseMixerObserver(
            callback=self.trigger_events_for_changed_values)
        self._observer.start()

    def get_volume(self):
        if self.sink is None:
            return None
        channels = self.sink.volume.values
        if channels.count(channels[0]) == len(channels):
            return int(channels[0] * 100.0)
        else:
            logger.info('Not all channels have the same volume')
            return None

    def set_volume(self, volume):
        if self.sink is None:
            return False
        self.pulse.volume_set_all_chans(self.sink, volume / 100.0)
        return True

    tmp = """
    def mixer_volume_to_volume(self, mixer_volume):
        volume = mixer_volume
        if self.volume_scale == 'cubic':
            volume = GstAudio.StreamVolume.convert_volume(
                GstAudio.StreamVolumeFormat.CUBIC,
                GstAudio.StreamVolumeFormat.LINEAR,
                volume / 100.0) * 100.0
        elif self.volume_scale == 'log':
            # Uses our own formula rather than GstAudio.StreamVolume.
            # convert_volume(GstAudio.StreamVolumeFormat.LINEAR,
            # GstAudio.StreamVolumeFormat.DB, mixer_volume / 100.0)
            # as the result is a DB value, which we can't work with as
            # self._mixer provides a percentage.
            volume = math.pow(10, volume / 50.0)
        volume = ((volume - self.min_volume) * 100.0
                  / (self.max_volume - self.min_volume))
        return int(volume)

    def volume_to_mixer_volume(self, volume):
        mixer_volume = (self.min_volume + volume *
                        (self.max_volume - self.min_volume) / 100.0)
        if self.volume_scale == 'cubic':
            mixer_volume = GstAudio.StreamVolume.convert_volume(
                GstAudio.StreamVolumeFormat.LINEAR,
                GstAudio.StreamVolumeFormat.CUBIC,
                mixer_volume / 100.0) * 100.0
        elif self.volume_scale == 'log':
            # Uses our own formula rather than GstAudio.StreamVolume.
            # convert_volume(GstAudio.StreamVolumeFormat.LINEAR,
            # GstAudio.StreamVolumeFormat.DB, mixer_volume / 100.0)
            # as the result is a DB value, which we can't work with as
            # self._mixer wants a percentage.
            mixer_volume = 50 * math.log10(mixer_volume)
        return int(mixer_volume)
"""

    def get_mute(self):
        if self.sink is None:
            return None
        else:
            return bool(self.sink.mute)

    def set_mute(self, mute):
        if self.sink is None:
            return False
        self.pulse.mute(mute)
        return True

    def trigger_events_for_changed_values(self, ev):
        if self.sink is None:
            return
        if ev.index != self.sink.index or ev.t != 'change':
            return
        old_volume, self._last_volume = self._last_volume, self.get_volume()
        old_mute, self._last_mute = self._last_mute, self.get_mute()

        if old_volume != self._last_volume:
            self.trigger_volume_changed(self._last_volume)

        if old_mute != self._last_mute:
            self.trigger_mute_changed(self._last_mute)

class PulseMixerObserver(threading.Thread):
    daemon = True
    name = 'PulseMixerObserver'

    def __init__(self, callback=None):
        super(PulseMixerObserver, self).__init__()
        self.running = True

        # Keep the mixer instance alive for the descriptors to work
        self.pulse = pulsectl.Pulse('PulseMixerObserver')
        self.callback = callback

    def stop(self):
        self.running = False

    def run(self):
        self.pulse.event_mask_set('sink')
        self.pulse.event_callback_set(self.callback)
        while self.running:
            self.pulse.event_listen(timeout=1)
