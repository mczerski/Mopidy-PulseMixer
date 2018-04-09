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
        sink = self.pulse.get_sink_by_name(self.sink_name)
        return sink

    def on_start(self):
        self._observer = PulseMixerObserver(
            callback=self.trigger_events_for_changed_values)
        self._observer.start()

    def _get_volume(self, sink):
        if sink is None:
            return None
        channels = sink.volume.values
        return int(channels[0] * 100.0)

    def get_volume(self):
        return self._get_volume(self._sink())

    def set_volume(self, volume):
        sink = self._sink()
        if sink is None:
            return False
        self.pulse.volume_set_all_chans(sink, volume / 100.0)
        return True

    def _get_mute(self, sink):
        if sink is None:
            return None
        else:
            return bool(sink.mute)

    def get_mute(self):
        return self._get_mute(self._sink())

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
        old_volume, self._last_volume = self._last_volume, self._get_volume(sink)
        old_mute, self._last_mute = self._last_mute, self._get_mute(sink)

        if old_volume != self._last_volume:
            self.trigger_volume_changed(self._last_volume)

        if old_mute != self._last_mute:
            self.trigger_mute_changed(self._last_mute)

class PulseMixerObserver(threading.Thread):
    daemon = True
    name = 'PulseMixerObserver'

    def __init__(self, callback):
        super(PulseMixerObserver, self).__init__()
        self.running = True
        self.callback = callback

    def stop(self):
        self.running = False

    def run(self):
        with pulsectl.Pulse('PulseMixerObserver') as pulse:
            pulse.event_mask_set('sink')
            pulse.event_callback_set(self.callback)
            while self.running:
                pulse.event_listen(timeout=1)
