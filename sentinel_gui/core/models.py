# encoding: utf-8
"""
models.py

Definition of models for core module

@author Carlos Garcia <cgarciaarano@gmail.com>
"""
import socket
from redis import StrictRedis


class RedisNode(object):

    """
    Represents a redis instance, it's a Redis connection and metadata. Base class.
    """

    def __init__(self, host='localhost', port=6379, metadata={}, **kwargs):
        self.conn = StrictRedis(host=host, port=port, **kwargs)
        self.metadata = metadata
        self.host = socket.gethostbyaddr(host)[0]
        self.set_metadata(metadata)

    def set_metadata(self, metadata):
        """
        Update internal __dict__
        """
        self.__dict__.update(metadata)

    def __str__(self):
        return '{host}:{port}'.format(host=self.host, port=self.conn.connection_pool.connection_kwargs['port'])

    @property
    def role(self):
        return "To be implemented"


class SentinelNode(RedisNode):

    """
    Represents a redis sentinel instance, it's a Redis connection and metadata.
    """

    def __init__(self, host='localhost', port=26379, metadata={}, **kwargs):
        super(SentinelNode, self).__init__(host=host, port=port, metadata=metadata, **kwargs)

        self.masters = []

    def discover_masters(self):
        """
        Returns a dict {'master_name1': {master data}, 'master_name2': {master data}}
        """
        return self.conn.sentinel_masters()

    def discover_master(self, master_name):
        """
        Returns a dict {master data}
        """
        return self.conn.sentinel_master(master_name)

    def discover_slaves(self, master_name):
        """
        Returns a list of slaves [{slave1 data}, {slave2 data}}
        """
        return self.conn.sentinel_slaves(master_name)

    def discover_sentinels(self, master_name):
        """
        Returns a list of sentinels, except self [{sentinel1 data}, {sentinel2 data}}
        """
        return self.conn.sentinel_sentinels(master_name)


class SentinelMaster(object):

    """
    A Sentinel master is comprised of a master RedisNode, optionally slaves RedisNode, and a group of SentinelNodes, and metadata
    """

    def __init__(self, name):
        """
        Creates a SentinelMaster instance. Just needs a name, but for discovery at least a SentinelNode is needed
        """
        self.name = name
        self.master = None
        self.slaves = {}
        self.sentinels = {}

    def discover(self):
        """
        Update internal __dict__
        """
        self.discover_master()
        self.discover_slaves()
        self.discover_sentinels()

    def __str__(self):
        return str(self.__dict__)

    def discover_master(self):
        # There's no master defined yet
        for _, sentinel in self.sentinels.items():
            master_data = sentinel.discover_master(self.name)
            if 'ip' in master_data and 'port' in master_data:
                self.set_master(RedisNode(host=master_data['ip'], port=master_data['port']))

    def discover_slaves(self):
        for _, sentinel in self.sentinels.items():
            for slave_data in sentinel.discover_slaves(self.name):
                if 'ip' in slave_data and 'port' in slave_data:
                    self.add_slave(RedisNode(host=slave_data['ip'], port=slave_data['port']))

    def discover_sentinels(self):
        new_sentinels = []
        for _, sentinel in self.sentinels.items():
            for sentinel_data in sentinel.discover_sentinels(self.name):
                if 'ip' in sentinel_data and 'port' in sentinel_data:
                    new_sentinels.append(SentinelNode(host=sentinel_data['ip'], port=sentinel_data['port']))

        # We can't add new sentinels while looping self.sentinels
        for new_sentinel in new_sentinels:
            self.add_sentinel(new_sentinel)

    def set_master(self, master):
        if str(master) != str(self.master):
            self.master = master
            print("Redis master in now {0}".format(self.master))
        else:
            print("Redis master {0} already set".format(self.master))

    def add_slave(self, slave):
        if not str(slave) in self.slaves:
            self.slaves[str(slave)] = slave
            print("New redis slave {0}".format(slave))
        else:
            print("Redis slave {0} already added".format(slave))

    def add_sentinel(self, sentinel):
        """
        Add SentinelNode which are monitoring this master
        """
        if not str(sentinel) in self.sentinels:
            self.sentinels[str(sentinel)] = sentinel
            print("New redis sentinel {0}".format(sentinel))
        else:
            print("Redis sentinel {0} already added".format(sentinel))


class SentinelManager():

    """
    Manages current Sentinel configuration
    """

    def __init__(self):
        self.masters = {}

    def add_sentinel_node(self, host, port=26379):
        """
        Add a sentinel node. Use it to perform autodiscovery, creating the discovered masters
        """
        # Create a sentinel connection to discover masters
        sentinel = SentinelNode(host=host, port=port)

        # Discover masters in the given sentinel.
        for master_name in sentinel.discover_masters().keys():
            # If not discovered yet, add it
            if not master_name in self.masters:
                self.masters[master_name] = SentinelMaster(master_name)

                # Link sentinel to current master
                self.masters[master_name].add_sentinel(sentinel)

                # Perform discovery on the given master
                self.masters[master_name].discover()

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
        for master_name in self.masters.keys():
            # Perform discovery on the given master
            self.masters[master_name].discover()
