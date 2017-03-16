# encoding: utf-8
"""
health.py

Classes to model health status in Redis nodes

@author Carlos Garcia <cgarciaarano@gmail.com>
"""
# std lib
from functools import reduce
from enum import IntEnum

# 3rd parties

# local


class HealthLevel(IntEnum):
    down = 0
    degraded = 1
    healthy = 2

    def __str__(self):
        """ String representation host:port"""
        if self is HealthLevel.down:
            return 'Down'
        elif self is HealthLevel.degraded:
            return 'Degraded'
        elif self is HealthLevel.healthy:
            return 'Healthy'


class Node(object):

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation host:port"""
        return self.unique_name

    def __eq__(self, other):
        if isinstance(other, Node):
            return (self.unique_name == other.unique_name)
        else:
            return False

    def __hash__(self):
        return hash(self.unique_name)

    def get_health(self):
        pass

    def is_healthy(self):
        return self.get_health() is HealthLevel.healthy

    def is_down(self):
        return self.get_health() is HealthLevel.down

    def is_degraded(self):
        return self.get_health() is HealthLevel.degraded


class Cluster(set):

    def __repr__(self):
        """ Object representation"""
        return "<{0}('{1}')>".format(self.__class__.__name__, "', '".join(self.__dict__.values()))

    def __str__(self):
        """ String representation"""
        return self.name

    def __eq__(self, other):
        """Object comparision"""
        if isinstance(other, Cluster):
            return (self.name == other.name)
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def get_health(self):
        """
        Return HealthLevel of its members.

         - down: All members are down
         - healthy: All members are healthy
         - degraded: Any other case
        """
        if self:
            aggr = (reduce(lambda x, y: x + y, map(lambda x: x.get_health(), self)) / (len(self)))

            if aggr == HealthLevel.down:
                return HealthLevel.down
            elif aggr == HealthLevel.healthy:
                return HealthLevel.healthy
            else:
                return HealthLevel.degraded
        return HealthLevel.down

    def is_healthy(self):
        return self.get_health() is HealthLevel.healthy

    def is_down(self):
        return self.get_health() is HealthLevel.down

    def is_degraded(self):
        return self.get_health() is HealthLevel.degraded
