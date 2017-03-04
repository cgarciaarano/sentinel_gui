# encoding: utf-8
"""
models.py

Definition of models for core module. It handles Redis nodes.

@author Carlos Garcia <cgarciaarano@gmail.com>
"""
# std lib
import socket
import os
import logging
import math
from pprint import pformat
from functools import reduce
from enum import IntEnum

# 3rd parties
from redis import StrictRedis
from redis.exceptions import ConnectionError

# local
from sentinel_gui.core.helpers import redis_warn

logger = logging.getLogger('sentinel_gui')


class HealthLevel(IntEnum):
    down = 0
    degraded = 1
    active = 2


class HealthMonitor(object):
    def get_health(self):
        pass

    def is_healthy(self):
        return self.get_health() is HealthLevel.active

    def is_degraded(self):
        return self.get_health() is HealthLevel.degraded

    def is_down(self):
        return self.get_health() is HealthLevel.down


class RedisNode(HealthMonitor):

    """
    Represents a redis instance, it's a Redis connection and metadata. Base class.
    """
    TIMEOUT = 0.1

    def __init__(self, host='localhost', port=6379, metadata={}, **kwargs):
        # Stored for reconnect
        self.host = host
        self.port = port
        self.kwargs = kwargs

        # Stored for debug
        self._metadata = metadata

        self.unique_name = '{host}:{port}'.format(host=socket.gethostbyaddr(self.host)[0], port=self.port)

        self.conn = StrictRedis(host=self.host, port=self.port, socket_timeout=RedisNode.TIMEOUT, **self.kwargs)

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation host:port"""
        return self.unique_name

    def __eq__(self, other):
        if isinstance(other, RedisNode):
            return (self.unique_name == other.unique_name)
        else:
            return False

    def __hash__(self):
        return hash(self.unique_name)

    def ping(self):
        with redis_warn(self):
            self.conn.ping()
            return True
        return False

    def is_active(self):
        return self.ping()

    def get_health(self):
        if self.is_active():
            return HealthLevel.active
        else:
            return HealthLevel.down

    def reconnect(self):
        """Connect to Redis"""
        self.conn = StrictRedis(host=self.host, port=self.port, socket_timeout=RedisNode.TIMEOUT, **self.kwargs)

        if self.ping():
            logger.info('Connected to Redis {0}'.format(self))
        else:
            logger.error('Failed connection to Redis {0}'.format(self))
            raise ConnectionError

    def serialize(self):
        """
        Return JSON representation
        E.g. {'unique_name': NAME,... (metadata)}
        """
        return {'unique_name': self.unique_name,
                'active': self.is_active(),
                'health': self.get_health(),
                'metadata': self._metadata
                }


class SentinelNode(RedisNode):

    """
    Represents a redis sentinel instance, it's a Redis connection, metadata and a list of
    managed masters.
    """

    def __init__(self, host='localhost', port=26379, metadata={}, **kwargs):
        super(SentinelNode, self).__init__(host=host, port=port, metadata=metadata, **kwargs)

        self.masters = set()

    def serialize(self):
        """
        Return JSON representation
        E.g. {'name': NAME,... (metadata), 'masters': [{'name': NAME; metadata...}, ] }
        """
        json_info = super(SentinelNode, self).serialize()

        json_info['masters'] = [{'name': master.name} for master in self.masters]

        return json_info

    def discover_masters(self):
        """
        Returns a dict of masters {'master1':  data, 'master2': data}.
        Docs are wrong: https://redis-py.readthedocs.io/en/latest/#redis.StrictRedis.sentinel_masters
        """
        with redis_warn(self):
            return self.conn.sentinel_masters()

    def discover_master(self, master_name):
        """
        Returns a dict {'master': data}
        """
        with redis_warn(self):
            return self.conn.sentinel_master(master_name)

    def discover_slaves(self, master_name):
        """
        Returns a list of slaves [{'slave1': data}, {'slave2': data}]
        """
        with redis_warn(self):
            return self.conn.sentinel_slaves(master_name)

    def discover_sentinels(self, master_name):
        """
        Returns a list of sentinels, except self [{'sentinel1': data}, {'sentinel2': data}]
        """
        with redis_warn(self):
            return self.conn.sentinel_sentinels(master_name)

    def link_master(self, master):
        """
        Add a reference to the given master
        """
        self.masters.add(master)


class SentinelMaster(HealthMonitor):

    """
    A Sentinel master is comprised of a master node RedisNode, optionally slaves RedisNode, and a group of SentinelNodes, and metadata
    """

    def __init__(self, name):
        """
        Creates a SentinelMaster instance. Just needs a name, but for discovery at least a SentinelNode is needed
        """
        self.name = name
        self.master_node = None
        self.slaves = set()
        self.sentinels = set()

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation"""
        return self.name

    def __eq__(self, other):
        """Object comparision"""
        if isinstance(other, SentinelMaster):
            return (self.name == other.name)
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def serialize(self):
        json_info = {
            'name': self.name,
            'master_node': self.master_node.serialize(),
            'slaves': [],
            'sentinels': [],
            'health': self.get_health(),
            'health_sentinels': self.get_health_sentinels(),
            'health_slaves': self.get_health_slaves(),
        }

        json_info['slaves'] = [slave.serialize() for slave in self.slaves]
        json_info['sentinels'] = [sentinel.serialize() for sentinel in self.sentinels]

        return json_info

    def get_health(self):
        """
        Return the HealthLevel of the master

         - down: if the master node or sentinels are down
         - degraded: if sentinels are degraded or slaves are degraded/down
         - active: if everything is active
        """
        h_master = self.get_health_masternode()
        h_sentinel = self.get_health_sentinels()
        h_slaves = self.get_health_slaves()
        logger.debug('Health value: {}'.format(int((h_master + h_sentinel + h_slaves)/3)))
        logger.debug('Return: {}'.format(int((h_master + h_sentinel + h_slaves)/3) is HealthLevel.active))

        if h_master is HealthLevel.down or h_sentinel is HealthLevel.down:
            return HealthLevel.down
        elif HealthLevel(int((h_master + h_sentinel + h_slaves)/3)) is HealthLevel.active:
            return HealthLevel.active
        else:
            return HealthLevel.degraded

    def get_health_masternode(self):
        return self.master_node.get_health()

    def get_health_slaves(self):
        """
        Return the HealthLevel of the slaves
            - down, if all slaves are down
            - degraded, if any slave is down
            - active, if all slaves are active
        """
        return HealthLevel(int(reduce(lambda x, y: x+y, map(lambda x: x.get_health(), self.slaves)) / len(self.slaves)))

    def get_health_sentinels(self):
        """Return the HealthLevel of the sentinels
            - down, if all sentinels are down
            - degraded, if any sentinels is down
            - active, if all sentinels are active
        """
        return HealthLevel(int(reduce(lambda x, y: x+y, map(lambda x: x.get_health(), self.sentinels)) / len(self.sentinels)))

    def are_sentinels_healthy(self):
        return self.get_health_sentinels() is HealthLevel.active

    def are_sentinels_degraded(self):
        return self.get_health_sentinels() is HealthLevel.degraded

    def are_sentinels_down(self):
        return self.get_health_sentinels() is HealthLevel.down

    def are_slaves_healthy(self):
        return self.get_health_slaves() is HealthLevel.active

    def are_slaves_degraded(self):
        return self.get_health_slaves() is HealthLevel.degraded

    def are_slaves_down(self):
        return self.get_health_slaves() is HealthLevel.down

    def discover(self):
        """
        Update internal __dict__
        """
        self.discover_master_node()
        self.discover_slaves()
        self.discover_sentinels()

    def get_active_sentinels(self):
        return (sentinel for sentinel in self.sentinels if sentinel.is_active())

    def discover_master_node(self):
        # There's no master node defined yet
        for sentinel in self.get_active_sentinels():
            master_data = sentinel.discover_master(self.name)
            self.master_node = RedisNode(host=master_data['ip'], port=master_data['port'], metadata=master_data)
            logger.info("{master}:Redis master node is now {node}".format(master=self, node=self.master_node))

    def discover_slaves(self):
        new_slaves = set()
        for sentinel in self.get_active_sentinels():
            for slave_data in sentinel.discover_slaves(self.name):
                new_slave = RedisNode(host=slave_data['ip'], port=slave_data['port'], metadata=slave_data)
                new_slaves.add(new_slave)
                logger.info("{master}:New redis slave {node}".format(master=self, node=new_slave))

        self.slaves = new_slaves

    def discover_sentinels(self):
        new_sentinels = set()
        for sentinel in self.get_active_sentinels():
            for sentinel_data in sentinel.discover_sentinels(self.name):
                new_sentinel = SentinelNode(host=sentinel_data['ip'], port=sentinel_data['port'], metadata=sentinel_data)
                new_sentinels.add(new_sentinel)
                logger.info("{master}:New redis slave {node}".format(master=self, node=new_sentinel))

        # We can't add new sentinels while looping self.sentinels
        self.sentinels.union(new_sentinels)

    def add_sentinel(self, sentinel):
        """
        Add SentinelNode which are monitoring this master
        """
        self.sentinels.add(sentinel)
        logger.info("{master}:New redis sentinel {node}".format(master=self, node=sentinel))
        # Add reference to the master in the sentinel node
        sentinel.link_master(self)

    def remove_sentinel(self, sentinel):
        """
        Remove sentinel host by reference
        """
        logger.info("{master}:Removing sentinel node {node}".format(master=self, node=sentinel))
        self.sentinels.remove(sentinel)


class SentinelManager(object):

    """
    Manages current Sentinel cluster configuration
    """

    def __init__(self):
        self.masters = set()

    def serialize(self):
        json_info = {'masters': []}

        for master in self.masters:
            json_info['masters'].append(master.serialize())

        return json_info

    def add_sentinel_node(self, host, port=26379):
        """
        Add a sentinel node. Use it to perform autodiscovery, creating the discovered masters
        """
        # Create a sentinel connection to discover masters
        sentinel = SentinelNode(host=host, port=port)

        # Discover masters in the given sentinel.
        for master_name, _ in sentinel.discover_masters().items():
            new_master = SentinelMaster(master_name)
            self.masters.add(new_master)

            # Link sentinel to current master
            new_master.add_sentinel(sentinel)

            # Perform discovery on the given master
            new_master.discover()

    def get_masters(self):
        self.update()
        return self.masters

    def update(self):
        """
        Updates the masters information. Should be smarter.
        """
        for master in self.masters:
            # Perform discovery on the given master
            master.discover()

        logger.debug('Current status:{0}{1}'.format(os.linesep, pformat(self.serialize())))
