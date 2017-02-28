# encoding: utf-8
"""
models.py

Definition of models for core module. It handles Redis nodes.

@author Carlos Garcia <cgarciaarano@gmail.com>
"""
import socket
from redis import StrictRedis
from redis.exceptions import ConnectionError
import logging

class RedisNode(object):

    """
    Represents a redis instance, it's a Redis connection and metadata. Base class.
    """

    def __init__(self, host='localhost', port=6379, metadata={}, **kwargs):
        self.conn = StrictRedis(host=host, port=port, **kwargs)
        self._metadata = metadata
        self.id = metadata['runid'] if 'runid' in metadata else '{host}:{port}'.format(host=host, port=port)
        self.host = socket.gethostbyaddr(host)[0]
        self.unique_name = '{host}:{port}'.format(host=self.host, port=port)
        self.set_metadata(metadata)

    def set_metadata(self, metadata):
        """
        Update internal __dict__
        """
        self.__dict__.update(metadata)

    def __str__(self):
        """ String representation host:port"""
        return self.unique_name

    def serialize(self):
        """
        Return JSON representation
        E.g. {'unique_name': NAME,... (metadata)}
        """
        return {'unique_name': self.unique_name,
                'id': self.id,
                'metadata': self._metadata
                }


class SentinelNode(RedisNode):

    """
    Represents a redis sentinel instance, it's a Redis connection, metadata and a list of
    managed masters.
    """

    def __init__(self, host='localhost', port=26379, metadata={}, **kwargs):
        super(SentinelNode, self).__init__(host=host, port=port, metadata=metadata, **kwargs)

        self.id = self.conn.info()['run_id']
        # References to the SentinelMasters managed by this node
        self.masters = []

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
        return self.conn.sentinel_masters()

    def discover_master(self, master_name):
        """
        Returns a dict {'master': data}
        """
        return self.conn.sentinel_master(master_name)

    def discover_slaves(self, master_name):
        """
        Returns a list of slaves [{'slave1': data}, {'slave2': data}]
        """
        return self.conn.sentinel_slaves(master_name)

    def discover_sentinels(self, master_name):
        """
        Returns a list of sentinels, except self [{'sentinel1': data}, {'sentinel2': data}]
        """
        return self.conn.sentinel_sentinels(master_name)

    def link_master(self, master):
        """
        Add a reference to the given master
        """
        if master not in self.masters:
            self.masters.append(master)


class SentinelMaster():

    """
    A Sentinel master is comprised of a master node RedisNode, optionally slaves RedisNode, and a group of SentinelNodes, and metadata
    """

    def __init__(self, name):
        """
        Creates a SentinelMaster instance. Just needs a name, but for discovery at least a SentinelNode is needed
        """
        self.name = name
        self.master_node = None
        self.slaves = []
        self.sentinels = []

    def serialize(self):
        json_info = {
            'name': self.name,
            'master_node': self.master_node.serialize(),
            'slaves': [],
            'sentinels': []
        }

        json_info['slaves'] = [slave.serialize() for slave in self.slaves]
        json_info['sentinels'] = [sentinel.serialize() for sentinel in self.sentinels]

        return json_info

    def discover(self):
        """
        Update internal __dict__
        """
        self.master_node = None
        self.slaves = []
        self.discover_master_node()
        self.discover_slaves()
        self.discover_sentinels()

    def __str__(self):
        return self.name

    def discover_master_node(self):
        # There's no master node defined yet
        for sentinel in self.sentinels:
            try:
                master_data = sentinel.discover_master(self.name)
                if 'ip' in master_data and 'port' in master_data:
                    self.set_master_node(RedisNode(host=master_data['ip'], port=master_data['port'], metadata=master_data))
            except ConnectionError:
                print("Connection error on {}".format(sentinel))
                self.remove_sentinel(sentinel)
                continue

    def discover_slaves(self):
        for sentinel in self.sentinels:
            try:
                for slave_data in sentinel.discover_slaves(self.name):
                    if 'ip' in slave_data and 'port' in slave_data:
                        self.add_slave(RedisNode(host=slave_data['ip'], port=slave_data['port'], metadata=slave_data))
            except ConnectionError:
                print("Connection error on {}".format(sentinel))
                self.remove_sentinel(sentinel)
                continue

    def discover_sentinels(self):
        new_sentinels = []
        for sentinel in self.sentinels:
            try:
                for sentinel_data in sentinel.discover_sentinels(self.name):
                    if 'ip' in sentinel_data and 'port' in sentinel_data:
                        new_sentinels.append(SentinelNode(host=sentinel_data['ip'], port=sentinel_data['port'], metadata=sentinel_data))
            except ConnectionError:
                print("Connection error on {}".format(sentinel))
                self.remove_sentinel(sentinel)
                continue

        # We can't add new sentinels while looping self.sentinels
        [self.add_sentinel(sentinel) for sentinel in new_sentinels]

    def set_master_node(self, master_node):
        if not self.master_node or master_node.unique_name != self.master_node.unique_name:
            self.master_node = master_node
            print("Redis master node is now {0}".format(self.master_node))
        else:
            print("Redis master node {0} already set".format(self.master_node))

    def add_slave(self, slave):
        if slave.unique_name not in [old_slave.unique_name for old_slave in self.slaves]:
            self.slaves.append(slave)
            print("New redis slave {0}".format(slave))
        else:
            print("Redis slave {0} already added".format(slave))

    def add_sentinel(self, sentinel):
        """
        Add SentinelNode which are monitoring this master
        """
        if sentinel.unique_name not in [old_sentinel.unique_name for old_sentinel in self.sentinels]:
            self.sentinels.append(sentinel)
            # Add reference to the master in the sentinel node
            sentinel.link_master(self)
            print("New redis sentinel {0}".format(sentinel))
        else:
            print("Redis sentinel {0} already added".format(sentinel))

    def remove_sentinel(self, sentinel):
        """
        Remove sentinel host by reference
        """
        print("Removing sentinel node {0}".format(sentinel))
        self.sentinels.remove(sentinel)


class SentinelManager():

    """
    Manages current Sentinel configuration
    """

    def __init__(self):
        self.masters = []

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
        for master_name, master_data in sentinel.discover_masters().items():
            # If not discovered yet, add it
            if not master_name in [old_master.name for old_master in self.masters]:
                new_master = SentinelMaster(master_name)
                self.masters.append(new_master)

                # Link sentinel to current master
                new_master.add_sentinel(sentinel)

                # Perform discovery on the given master
                new_master.discover()

    def get_masters(self):
        """
        Return the current masters configuration. Should be smarter.
        """
        self.update()
        return self.masters

    def update(self):
        """
        Updates the masters information. Should be smarter.
        """
        for master in self.masters:
            # Perform discovery on the given master
            master.discover()
