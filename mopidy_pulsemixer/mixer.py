from __future__ import unicode_literals

import logging
import threading

import pulsectl

from mopidy import mixer

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
        self._last_volume = None
        self._last_mute = None
        logger.info(
            'Mixing using Pulseaudio, sink "%s".',
            self.sink_name)

    def _sink(self):
        sinks = self.pulse.sink_list()
        for sink in sinks:
            if sink.name == self.sink_name:
                return sink
        logger.error(
                'Could not find Pulseaudio sink %(sink)s. '
                'Available sinks include: %(sinks)s' % {
                    'sink': self.sink_name,
                    'sinks': ', '.join([sink.name for sink in sinks]),
                })
        return None

    def on_start(self):
        self._observer = PulseMixerObserver(
            callback=self.trigger_events_for_changed_values)
        self._observer.start()

    def get_volume(self):
        sink = self._sink()
        if sink is None:
            return None
        channels = sink.volume.values
        if channels.count(channels[0]) == len(channels):
            return int(channels[0] * 100.0)
        else:
            logger.info('Not all channels have the same volume')
            return None

    def set_volume(self, volume):
        sink = self._sink()
        if sink is None:
            return False
        self.pulse.volume_set_all_chans(sink, volume / 100.0)
        return True

    def get_mute(self):
        sink = self._sink()
        if sink is None:
            return None
        else:
            return bool(sink.mute)

    def set_mute(self, mute):
        sink = self._sink()
        if sink is None:
            return False
        self.pulse.mute(mute)
        return True

    def trigger_events_for_changed_values(self, ev):
        sink = self._sink()
        if sink is None:
            return
        if ev.index != sink.index or ev.t != 'change':
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
