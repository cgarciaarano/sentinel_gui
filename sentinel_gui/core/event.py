# encoding: utf-8
"""
utils.py

Common utilities to handle core tasks, as decoding redis messages

@author Carlos Garcia <cgarciaarano@gmail.com>
"""
# std lib
import logging
import re

# 3rd parties
from redis._compat import nativestr


logger = logging.getLogger('sentinel_gui')


class SentinelEvent(object):

    def __init__(self, message):
        self._callback = None

        message = {k: nativestr(v) for k, v in message.items()}

        self.channel = message['channel']
        try:
            # Parse response, as the library doesn't
            self._data = message['data']
        except:
            logger.error("Can't create event from {e}".format(e=message))
            raise

        self.role = None
        self.name = None
        self.ip = None
        self.port = None
        self.master_name = None
        self.master_ip = None
        self.master_port = None
        self._parse()

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation host:port"""
        return self.channel

    def run(self, f):
        if f:
            return f()

    def _parse(self):
        """
        Parse sentinel message. There are messages with different responses
        """
        if self.channel == 'switch-master':
            pattern = re.compile('(?P<mastername>\w*) (?P<oldmasterip>(\d+\.?)+) (?P<oldmasterport>\d+) (?P<newmasterip>(\d+\.?)+) (?P<newmasterport>\d+)')

            m = pattern.match(self._data)

            if m:
                self.role = 'master'
                self.name = m.group('mastername')
                self.ip = m.group('newmasterip')
                self.port = m.group('newmasterport')
                self.master_name = m.group('mastername')

        elif self.channel not in ('+tilt', '-tilt'):
            pattern = re.compile('^(?P<role>\w*) (?P<name>(\d+\.?)+:\d+) (?P<ip>(\d+\.?)+) (?P<port>\d+)( @ (?P<mastername>\w*) (?P<masterip>(\d+\.?)+) (?P<masterport>\d+))?')
            m = pattern.match(self._data)

            if m:
                self.role = m.group('role')
                self.name = m.group('name')
                self.ip = m.group('ip')
                self.port = m.group('port')
                if m.group('mastername'):
                    self.master_name = m.group('mastername')
                    self.master_ip = m.group('masterip')
                    self.master_port = m.group('masterport')

    def is_for(self, master_name):
        return self.master_name and self.master_name == master_name
