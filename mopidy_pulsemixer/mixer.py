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
        self._last_volume = None
        self._last_mute = None

    def on_start(self):
        self._observer = PulseMixerObserver(
            sink_name=self.config['pulsemixer'].get('sink'),
            callback=self.trigger_events_for_changed_values)
        self._observer.start()

    def get_volume(self):
        return self._observer.get_volume()

    def set_volume(self, volume):
        return self._observer.set_volume(volume)

    def get_mute(self):
        return self._observer.get_mute()

    def set_mute(self, mute):
        return self._observer.set_mute(mute)

    def trigger_events_for_changed_values(self):
        old_volume, self._last_volume = self._last_volume, self.get_volume()
        old_mute, self._last_mute = self._last_mute, self.get_mute()

        if old_volume != self._last_volume:
            self.trigger_volume_changed(self._last_volume)

        if old_mute != self._last_mute:
            self.trigger_mute_changed(self._last_mute)

class PulseMixerObserver(threading.Thread):
    daemon = True
    name = 'PulseMixerObserver'

    def __init__(self, sink_name, callback):
        super(PulseMixerObserver, self).__init__()
        self._running = True
        self._changed = False
        self._callback = callback
        self._sink_name = sink_name
        self._sink = None
        self._volume = None
        self._mute = None

    def _getSink(self, pulse):
        if self._sink_name is not None:
            self._sink = pulse.get_sink_by_name(self._sink_name)
        else:
            sink_list = pulse.sink_list()
            if len(sink_list) > 0:
                self._sink = sink_list[0]
                self._sink_name = self._sink.name
            else:
                self._sink = None

    def callback(self, ev):
        self._changed = self._sink is not None and ev.t == "change" and ev.index == self._sink.index
        if self._changed:
            raise pulsectl.PulseLoopStop()

    def changed(self, pulse):
	if self._changed:
	    self._changed = False
	    self._getSink(pulse)
	    self._callback()

    def update(self, pulse):
	if self._volume is not None:
	    pulse.volume_set_all_chans(self._sink, self._volume / 100.0)
	    self._volume = None
	if self._mute is not None:
	    pulse.mute(self._mute)
	    self._mute = None

    def stop(self):
        self._running = False

    def run(self):
        with pulsectl.Pulse('PulseMixerObserver') as pulse:
            self._getSink(pulse)
            if self._sink is None:
                logger.error('Failed to open sink, sink "%s".', self._sink_name)
                return
            logger.info('Mixing using Pulseaudio, sink "%s".', self._sink.name)
            pulse.event_mask_set('sink')
            pulse.event_callback_set(self.callback)
            self.update(pulse)
            while self._running:
                try:
                    pulse.event_listen(timeout=1)
                except pulsectl.PulseLoopStop:
                    pass
                self.changed(pulse)
                self.update(pulse)

    def get_volume(self):
        if self._sink is None:
            return None
        channels = self._sink.volume.values
        return int(channels[0] * 100.0)

    def set_volume(self, volume):
        self._volume = volume
        if self._sink is None:
            return False
        return True

    def get_mute(self):
        if self._sink is None:
            return None
        else:
            return bool(self._sink.mute)

    def set_mute(self, mute):
        self._mute = mute
        if self._sink is None:
            return False
        return True

