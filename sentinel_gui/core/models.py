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
from pprint import pformat
from contextlib import contextmanager

# 3rd parties
from redis import StrictRedis
from redis.exceptions import ConnectionError

# local
from sentinel_gui import settings
from sentinel_gui.core.health import Node, Cluster, HealthLevel
from sentinel_gui.core.event import SentinelEvent
from sentinel_gui.web import socketio

logger = logging.getLogger('sentinel_gui')


class Redis(Node):

    """
    Represents a redis instance, it's a Redis connection and metadata. Base class.
    """

    def __init__(self, host='localhost', port=6379, metadata={}, **kwargs):
        # Stored for reconnect
        try:
            self.host = socket.gethostbyname(host)
        except:
            logger.warn("Can't resolve hostname {}. Let Redis fail.".format(host))
            self.host = host
        self.port = port
        self.kwargs = kwargs

        try:
            self.hostname = socket.gethostbyaddr(self.host)[0]
        except:
            logger.warn("Can't resolve IP address {}. Fallback to IP.".format(self.host))
            self.hostname = host
        self.active = True
        # Stored for debug
        self._metadata = metadata

        self.unique_name = '{host}:{port}'.format(host=self.host, port=self.port)

        self.conn = StrictRedis(host=self.host, port=self.port, socket_timeout=settings.REDIS_SOCKET_TIMEOUT, **self.kwargs)

        # Test connection
        self.ping()

    def ping(self):
        with self.redis_warn():
            self.conn.ping()
            return True
        return False

    def is_active(self):
        return self.active

    def get_health(self):
        if self.is_active():
            return HealthLevel.healthy
        else:
            return HealthLevel.down

    def reconnect(self):
        """Connect to Redis"""
        self.conn = StrictRedis(host=self.host, port=self.port, socket_timeout=Redis.TIMEOUT, decode_responses=True, **self.kwargs)

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

    @contextmanager
    def redis_warn(self):
        try:
            yield
        except ConnectionError:
            logger.warn("Can't connect to redis instance {}".format(self))
            self.active = False


class SentinelNode(Redis):

    """
    Represents a redis sentinel instance, it's a Redis connection, metadata and a list of
    managed masters.
    """

    def __init__(self, host='localhost', port=26379, metadata={}, **kwargs):
        super(SentinelNode, self).__init__(host=host, port=port, metadata=metadata, **kwargs)

        self.masters = Cluster()

    def serialize(self):
        """
        Return JSON representation
        E.g. {'name': NAME,... (metadata), 'masters': [{'name': NAME; metadata...}, ] }
        """
        json_info = super(SentinelNode, self).serialize()

        json_info['masters'] = [{'name': master.name} for master in self.masters]

        return json_info

    def is_synced(self):
        """ A Sentinel node is active if it sees more sentinels than quorum-1"""
        # TODO Implement
        return self.active

    def discover_masters(self):
        """
        Returns a dict of masters {'master1':  data, 'master2': data}.
        Docs are wrong: https://redis-py.readthedocs.io/en/latest/#redis.StrictRedis.sentinel_masters
        """
        with self.redis_warn():
            return self.conn.sentinel_masters()

    def discover_master(self, master_name):
        """
        Returns a dict {'master': data}
        """
        with self.redis_warn():
            return self.conn.sentinel_master(master_name)

    def discover_slaves(self, master_name):
        """
        Returns a list of slaves [{'slave1': data}, {'slave2': data}]
        """
        with self.redis_warn():
            return self.conn.sentinel_slaves(master_name)

    def discover_sentinels(self, master_name):
        """
        Returns a list of sentinels, except self [{'sentinel1': data}, {'sentinel2': data}]
        """
        with self.redis_warn():
            return self.conn.sentinel_sentinels(master_name)

    def link_master(self, master):
        """
        Add a reference to the given master
        """
        self.masters.add(master)


class SentinelMaster(Node):

    """
    A Sentinel master is comprised of a master node Redis, optionally slaves Redis, a group of SentinelNodes,
    a pubsub connection to any active sentinel and metadata
    """

    def __init__(self, name):
        """
        Creates a SentinelMaster instance. Just needs a name, but for discovery at least a SentinelNode is needed
        """
        self.unique_name = name
        self.name = name
        self.master_node = None
        self.slaves = Cluster()
        self.sentinels = Cluster()

        # Pubsub connection to any sentinel
        self.listener = None
        self.listen_thread = None

    def serialize(self):
        json_info = {
            'name': self.name,
            'master_node': self.master_node.serialize(),
            'slaves': [],
            'sentinels': [],
            'health': self.get_health(),
            'health_sentinels': self.sentinels.get_health(),
            'health_slaves': self.slaves.get_health(),
        }

        json_info['slaves'] = [slave.serialize() for slave in self.slaves]
        json_info['sentinels'] = [sentinel.serialize() for sentinel in self.sentinels]

        return json_info

    def get_health(self):
        """
        Return HealthLevel of this master.

            - down: If master is down or sentinels are down
            - active: If everything is active
            - degraded: Any other case
        """
        if self.master_node.is_down() or self.sentinels.is_down():
            return HealthLevel.down
        elif self.master_node.is_healthy() and self.sentinels.is_healthy() and self.slaves.is_healthy():
            return HealthLevel.healthy
        else:
            return HealthLevel.degraded

    def discover(self):
        """
        Update internal __dict__
        """
        self.discover_master_node()
        self.discover_slaves()
        self.discover_sentinels()

        logger.debug('{master}:Current status:{sep}{data}'.format(master=self, sep=os.linesep, data=pformat(self.serialize())))

    def get_active_sentinels(self):
        """
        Returns active Sentinels
        """
        return (sentinel for sentinel in self.sentinels if sentinel.is_active())

    def get_synced_sentinel(self):
        """
        Returns one active and synced Sentinel
        """
        return [sentinel for sentinel in self.get_active_sentinels() if sentinel.is_synced()][0:1]

    def discover_master_node(self):
        """
        Discover master node, returning True if any change has been detected
        """
        # There's no master node defined yet
        for sentinel in self.get_synced_sentinel():
            master_data = sentinel.discover_master(self.name)
            # master_data could be None if the current sentinel is disconnected
            if master_data:
                new_master = Redis(host=master_data['ip'], port=master_data['port'], metadata=master_data)
                logger.debug("{master}:New master {n}".format(master=self, n=new_master))
                self.master_node = new_master
                logger.info("{master}:Redis master node is now {node}".format(master=self, node=self.master_node))
        # FIXME
        self.notify()

    def discover_slaves(self):
        """
        Discover slaves, returning True if any change has been detected
        """
        new_slaves = Cluster()
        for sentinel in self.get_synced_sentinel():
            for slave_data in sentinel.discover_slaves(self.name):
                new_slave = Redis(host=slave_data['ip'], port=slave_data['port'], metadata=slave_data)
                new_slaves.add(new_slave)
                logger.info("{master}:New redis slave {node}".format(master=self, node=new_slave))

        self.slaves = new_slaves
        # FIXME
        self.notify()

    def discover_sentinels(self):
        """
        Discover sentinels, returning True if any change has been detected
        """
        new_sentinels = Cluster()

        # If all sentinels are down, this will retry reconnection
        current_sentinels = self.get_synced_sentinel()
        if not current_sentinels:
            logger.debug("{master}:All sentinels down, retrying connections".format(master=self))
            current_sentinels = self.sentinels

        for sentinel in current_sentinels:
            for sentinel_data in sentinel.discover_sentinels(self.name):
                new_sentinel = SentinelNode(host=sentinel_data['ip'], port=sentinel_data['port'], metadata=sentinel_data)
                new_sentinels.add(new_sentinel)
                logger.info("{master}:New redis slave {node}".format(master=self, node=new_sentinel))

        # FIXME If a sentinel dies, the update is not inserted, so it doesn't reflect the down state
        # We can't add new sentinels while looping self.sentinels
        [self.add_sentinel(sentinel) for sentinel in new_sentinels]
        # FIXME
        self.notify()

    def set_listener(self):
        """
        Establish a pubsub connection against the first active sentinel.
        """
        if self.listen_thread:
            self.listen_thread.stop()

        for sentinel in self.get_synced_sentinel():
            # decode_responses needed to parse pubsub messages
            self.listener = sentinel.conn.pubsub(ignore_subscribe_messages=True)
            logger.info('{master}:Subscribing to stream in sentinel {node}'.format(master=self, node=sentinel))
            self.listener.psubscribe(**{'*': self.process_sentinel_messages})
            self.listen_thread = self.listener.run_in_thread(sleep_time=settings.REDIS_POLLING_PERIOD)
            break
        else:
            self.listener = None
            self.listen_thread = None

    def process_sentinel_messages(self, msg):
        """
        Process the pubsub messages from the active sentinel
        """
        mapping = {
            '+reset-master': self.discover,
            '+slave': self.discover_slaves,
            '+failover-state-reconf-slave': None,
            '+failover-detected': None,
            '+slave-reconf-sent': None,
            '+slave-reconf-inprog': None,
            '+slave-reconf-done': None,
            '-dup-sentinel': None,
            '+sentinel': self.discover_sentinels,
            '+sdown': self.discover,
            '-sdown': None,
            '+odown': None,
            '-odown': None,
            '+new-epoch': None,
            '+try-failover': None,
            '+elected-leader': None,
            '+failover-state-select-slave': None,
            'no-good-slave': None,
            'selected-slave': None,
            'failover-state-send-slaveof-noone': None,
            'failover-end-for-timeout': None,
            'failover-end': None,
            'switch-master': self.discover,
            '+tilt': None,
            '-tilt': None,
            '+fix-slave-config': None,
            '+reboot': self.discover,
        }

        logger.debug('{master}: Message received: {msg}'.format(master=self, msg=msg))
        event = SentinelEvent(msg, src=self.unique_name)

        try:
            event.run(mapping.get(event.channel, None))
        except:
            logger.error('{master}: Message unkwown: {m}'.format(master=self, m=msg))

    def notify(self):
        """
        Notify changes via WS
        """
        socketio.emit("update_message", namespace='/test')
        logger.debug('{master}: emit sent'.format(master=self))

    def add_sentinel(self, sentinel):
        """
        Add SentinelNode which are monitoring this master
        """
        self.sentinels.add(sentinel)
        logger.info("{master}:New redis sentinel {node}".format(master=self, node=sentinel))
        # Add reference to the master in the sentinel node
        sentinel.link_master(self)

        if not self.listener:
            self.set_listener()

    def remove_sentinel(self, sentinel):
        """
        Remove sentinel host by reference
        """
        logger.info("{master}:Removing sentinel node {node}".format(master=self, node=sentinel))
        self.sentinels.remove(sentinel)
        self.set_listener()


class SentinelManager(object):

    """
    Manages current Sentinel cluster configuration
    """

    def __init__(self):
        self.masters = Cluster()

    def reset(self):
        self.__init__()

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
        masters = sentinel.discover_masters()
        if masters:
            for master_name in masters.keys():
                new_master = SentinelMaster(master_name)
                self.masters.add(new_master)

                # Link sentinel to current master
                new_master.add_sentinel(sentinel)

                # Perform discovery on the given master
                new_master.discover()
            return True
        return False

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
