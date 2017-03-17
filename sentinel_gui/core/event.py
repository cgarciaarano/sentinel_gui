# encoding: utf-8
"""
utils.py

Common utilities to handle core tasks, as decoding redis messages

    Redis Sentinel messages (from https://redis.io/topics/sentinel)
    ===============================================================

    instance detail = <instance-type> <name> <ip> <port> @ <master-name> <master-ip> <master-port>

    +reset-master <instance details> -- The master was reset.
    +slave <instance details> -- A new slave was detected and attached.
    +failover-state-reconf-slaves <instance details> -- Failover state changed to reconf-slaves state.
    +failover-detected <instance details> -- A failover started by another Sentinel or any other external entity was detected (An attached slave turned into a master).
    +slave-reconf-sent <instance details> -- The leader sentinel sent the SLAVEOF command to this instance in order to reconfigure it for the new slave.
    +slave-reconf-inprog <instance details> -- The slave being reconfigured showed to be a slave of the new master ip:port pair, but the synchronization process is not yet complete.
    +slave-reconf-done <instance details> -- The slave is now synchronized with the new master.
    -dup-sentinel <instance details> -- One or more sentinels for the specified master were removed as duplicated (this happens for instance when a Sentinel instance is restarted).
    +sentinel <instance details> -- A new sentinel for this master was detected and attached.
    +sdown <instance details> -- The specified instance is now in Subjectively Down state.
    -sdown <instance details> -- The specified instance is no longer in Subjectively Down state.
    +odown <instance details> -- The specified instance is now in Objectively Down state.
    -odown <instance details> -- The specified instance is no longer in Objectively Down state.
    +new-epoch <instance details> -- The current epoch was updated.
    +try-failover <instance details> -- New failover in progress, waiting to be elected by the majority.
    +elected-leader <instance details> -- Won the election for the specified epoch, can do the failover.
    +failover-state-select-slave <instance details> -- New failover state is select-slave: we are trying to find a suitable slave for promotion.
    no-good-slave <instance details> -- There is no good slave to promote. Currently we'll try after some time, but probably this will change and the state machine will abort the failover at all in this case.
    selected-slave <instance details> -- We found the specified good slave to promote.
    failover-state-send-slaveof-noone <instance details> -- We are trying to reconfigure the promoted slave as master, waiting for it to switch.
    failover-end-for-timeout <instance details> -- The failover terminated for timeout, slaves will eventually be configured to replicate with the new master anyway.
    failover-end <instance details> -- The failover terminated with success. All the slaves appears to be reconfigured to replicate with the new master.
    switch-master <master name> <oldip> <oldport> <newip> <newport> -- The master new IP and address is the specified one after a configuration change. This is the message most external users are interested in.
    +tilt -- Tilt mode entered.
    -tilt -- Tilt mode exited.

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
            pattern = re.compile('^(?P<role>\w*) (?P<name>(\d+\.?)+:\d+|\w+) (?P<ip>(\d+\.?)+) (?P<port>\d+)( @ (?P<mastername>\w*) (?P<masterip>(\d+\.?)+) (?P<masterport>\d+))?')
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
        return self.name and self.name == master_name
