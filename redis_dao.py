import os
import subprocess
from collections import defaultdict
import redis
import pickle


class RedisDAO:
    """
    Base class of Redis Data Access Object
    """
    __slots__ = {'name', 'conn', 'port', 'host'}

    def __init__(self, name=None, host='localhost', port=6379, *args, **kwargs):
        self.name = name
        self.host = host
        self.port = port
        self.conn = redis.Redis(host=host, port=port, *args, **kwargs)

        # auto start redis server when server is not set-up yet.
        self.ping()

    @staticmethod
    def __valueEncode__(value):
        if not value or isinstance(value, (int, float, str)):
            return value
        else:
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def __valueDecode__(b):
        try:
            return pickle.loads(b)
        except:
            return b.decode('utf-8')

    def __getitem__(self, item):
        result = self.conn.get(item)
        return self.__valueDecode__(result)

    def __setitem__(self, key, value):
        return self.conn.set(key, self.__valueEncode__(value))

    def __contains__(self, item):
        return bool(self.conn.get(self.__valueEncode__(item)))

    def ping(self):
        try:
            return self.conn.ping()
        except redis.exceptions.ConnectionError:
            subprocess.Popen(["setsid", "redis-server", '--bind', self.host, '--port', str(self.port)],
                             stdout=open(os.devnull, "w"),
                             stderr=subprocess.STDOUT)
            return False


# Todo implement NamedRedisDAO, which is the base class of RedisSet and RedisList


class RedisSet(RedisDAO):
    def add(self, value):
        return int(self.conn.sadd(self.name, self.__valueEncode__(value)))

    def pop(self):
        return self.__valueDecode__(self.conn.spop(self.name))

    def remove(self, value):
        return int(self.conn.srem(self.name, self.__valueEncode__(value)))

    def items(self):
        return {self.__valueDecode__(_) for _ in self.conn.smembers(self.name)}

    def __contains__(self, item):
        return bool(self.conn.sismember(self.name, self.__valueEncode__(item)))

    def __len__(self):
        return len(self.conn.smembers(self.name))

    def clear(self):
        return self.conn.delete(self.name)


class RedisSetDict(defaultdict):
    """
    defaultdict mapping to RedisSet objects

    :param host: redis server host name

    :param port: redis server port number

    :param db: redis server database index

    :param kwargs: other parameters

    """
    __slots__ = {'host', 'port', 'db'}

    def __init__(self, host='localhost', port=6379, db=0, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.db = db

    def __missing__(self, key):
        ret = self[key] = RedisSet(key, self.host, self.port, db=self.db)
        return ret


class RedisList(RedisDAO):
    # Todo tests and further implements are required
    def __init__(self, key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = key
        self.push = self.append

    def append(self, item):
        self.conn.rpush(self.name, self.__valueEncode__(item))

    def appendleft(self, item):
        self.conn.lpush(self.name, self.__valueEncode__(item))

    def pop(self, block=False):
        if block:
            return self.__valueDecode__(self.conn.brpop(self.name))
        else:
            return self.__valueDecode__(self.conn.rpop(self.name))

    def popleft(self, block=False):
        if block:
            return self.__valueDecode__(self.conn.blpop(self.name))
        else:
            return self.__valueDecode__(self.conn.lpop(self.name))

    def extend(self, iterable):
        for item in iterable:
            self.append(item)

    def extendleft(self, iterable):
        for item in iterable:
            self.appendleft(item)

    def remove(self, item):
        self.conn.lrem(self.name, self.__valueEncode__(item))

    def __getitem__(self, key):
        """
        [] operator function (step is not supported)
        :param key: int or slice
        :return:
        """
        if isinstance(key, int):
            return self.__valueDecode__(self.conn.lindex(self.name, key))
        elif isinstance(key, slice):
            return self.__valueDecode__(self.conn.lrange(self.name, key.start, key.stop))
        else:
            raise TypeError("RedisList expect a int index, but type:{} is given".format(str(type(item))))

    def __setitem__(self, key, value):
        if isinstance(item, int):
            return self.conn.lset(self.name, item, self.__valueEncode__(value))
        else:
            raise TypeError("RedisList expect a int index, but type:{} is given".format(str(type(item))))

    def __iter__(self):
        # Todo implement this
        pass


class __Test__:
    def __init__(self):
        self.a = 1
        self.b = 2

    def __str__(self):
        return 'a:{}\tb:{}'.format(self.a, self.b)


if __name__ == "__main__":
    # rdict = RedisDAO(port=7878)
    # rdict.conn.flushall()
    # rdict['a'] = 1
    # print(rdict['a'])
    # print(rdict['b'])
    # print('a' in rdict)
    # print('b' in rdict, '\n')
    #
    redisSetDict = RedisSetDict(port=7777, db=1)
    # redisSetDict[1234].add(1)
    # redisSetDict[1234].add(2)
    # print(redisSetDict[1234].add(2))
    # print(redisSetDict[1234].add(3))
    # print(3 in redisSetDict[1234])
    # print(4 in redisSetDict[1234])
    # print(redisSetDict[1234].remove(3))
    # print(3 in redisSetDict[1234])
    test = __Test__()
    print(redisSetDict[0].conn.get('fuck'))
    print(redisSetDict[0].add(test))
    print(redisSetDict[0].add(test))
    print(redisSetDict[0].add(1))
    print(redisSetDict[0].add(1.1))
    print(redisSetDict[0].add("1.1"))
    print(redisSetDict[0].remove('1.1'))
    print(test in redisSetDict[0])
    print(redisSetDict[0].items())
    for item in redisSetDict[0].items():
        print(item)
    # redisSetDict[0].conn.flushall()