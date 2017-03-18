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


def _parse_default(message):
    """
    Parse the instance detail, as it's the defaault in most messages
    """
    (role, node_name, node_ip, node_port, master_name, master_ip, master_port) = (None, None, None, None, None, None, None)

    pattern = re.compile('^(?P<role>\w*) (?P<node_name>(\d+\.?)+:\d+|\w+) (?P<ip>(\d+\.?)+) (?P<port>\d+)( @ (?P<mastername>\w*) (?P<masterip>(\d+\.?)+) (?P<masterport>\d+))?')
    m = pattern.match(message)

    if m:
        role = m.group('role')
        node_name = m.group('node_name')
        node_ip = m.group('ip')
        node_port = m.group('port')
        # If the role is not master, it has @ section
        if m.group('mastername'):
            master_name = m.group('mastername')
            master_ip = m.group('masterip')
            master_port = m.group('masterport')
        # The role is master, the @ section is ommited in message
        else:
            master_name = m.group('node_name')
            master_ip = m.group('ip')
            master_port = m.group('port')

    return (role, node_name, node_ip, node_port, master_name, master_ip, master_port)


def _parse_switch_master(message):
    """
    Parse switch_master message
    """
    (role, node_name, node_ip, node_port, master_name, master_ip, master_port) = (None, None, None, None, None, None, None)

    pattern = re.compile('(?P<mastername>\w*) (?P<oldmasterip>(\d+\.?)+) (?P<oldmasterport>\d+) (?P<newmasterip>(\d+\.?)+) (?P<newmasterport>\d+)')
    m = pattern.match(message)

    if m:
        self.role = 'master'
        self.node_name = m.group('mastername')
        self.node_ip = m.group('newmasterip')
        self.node_port = m.group('newmasterport')
        self.master_name = m.group('mastername')
        self.master_ip = m.group('newmasterip')
        self.master_port = m.group('newmasterport')

    return (role, node_name, node_ip, node_port, master_name, master_ip, master_port)


class SentinelEvent(object):

    PARSE_CALLBACKS = {
        '+reset-master': _parse_default,
        '+slave': _parse_default,
        '+failover-state-reconf-slave': _parse_default,
        '+failover-detected': _parse_default,
        '+slave-reconf-sent': _parse_default,
        '+slave-reconf-inprog': _parse_default,
        '+slave-reconf-doner': _parse_default,
        '-dup-sentinel': _parse_default,
        '+sentinel': _parse_default,
        '+sdown': _parse_default,
        '-sdown': _parse_default,
        '+odown': _parse_default,
        '-odown': _parse_default,
        '+new-epoch': _parse_default,
        '+try-failover': _parse_default,
        '+elected-leader': _parse_default,
        '+failover-state-select-slaven': _parse_default,
        'no-good-slave': _parse_default,
        'selected-slave': _parse_default,
        'failover-state-send-slaveof-noone': _parse_default,
        'failover-end-for-timeout': _parse_default,
        'failover-end': _parse_default,
        'switch-master': _parse_switch_master,
        '+tilt': None,
        '-tilt': None,
        '+fix-slave-config': _parse_default,
    }

    def __init__(self, message, src):
        self._callback = None

        # Clean message from Redis, as the library did not do it
        message = {k: nativestr(v) for k, v in message.items()}

        self.channel = message['channel']
        self.src_master = src

        # Get payload from message
        try:
            self._data = message['data']
        except:
            logger.error("Can't create event from {e}".format(e=message))
            raise

        # Check for parsing implementation for this event
        if self.channel not in self.__class__.PARSE_CALLBACKS.keys():
            raise NotImplementedError("Event {0} is not implemented".format(self.channel))

        # Initialize attribs
        self.role = None
        self.node_name = None
        self.node_ip = None
        self.node_port = None
        self.master_name = None
        self.master_ip = None
        self.master_port = None
        self.callbacks = self.__class__.PARSE_CALLBACKS
        # Populate available attribs
        self._parse()

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation host:port"""
        return self.channel

    def run(self, f):
        if f:
            if self.is_for(self.src_master):
                return f()
            else:
                logger.info("Ignoring event, emitted for another master")

    def _parse(self):
        # Populate attribs, if available
        (self.role, self.node_name, self.node_ip, self.node_port, self.master_name, self.master_ip, self.master_port) = self.callbacks.get(self.channel)(message=self._data)

    def is_for(self, master_name):
        return self.master_name and self.master_name == master_name
