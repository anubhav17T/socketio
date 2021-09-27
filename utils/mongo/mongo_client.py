import re
import time
from asyncio.log import logger
from pymongo import MongoClient, WriteConcern
from utils.properties import keysInformation


class MongoConfig:
    def __new__(cls):
        cls.not_master = re.compile(r'not master')
        if keysInformation["mongodb.auth.enabled"] == 'true':
            if not hasattr(cls, 'instance'):
                cls.instance = super(MongoConfig, cls).__new__(cls)
                cls.instance.client = MongoClient(keysInformation["mongodb.server.url"])
            return cls.instance
        else:
            if not hasattr(cls, 'instance'):
                cls.instance = super(MongoConfig, cls).__new__(cls)
                # MongoClient(keysInformation["mongodb.server.url"])
                cls.instance.client = MongoClient('mongodb://' + 'localhost:27017')
            return cls.instance

    def reconnect(self):
        timer = 3
        logger.warning("######## old mongoConnection closed #######")
        logger.warning("######## reconnecting client ########")
        for repeat in range(4):
            time.sleep(timer)
            self.instance.client.close()
            self.instance.client = MongoClient(keysInformation["mongodb.server.url"])
            timer = timer * 2
            return self.instance.client

    def get_db(self, database_name):
        return self.instance.client[database_name]

    def insert(self, database, collection, document):
        try:
            return self.get_db(database).get_collection(collection).with_options(
                write_concern=WriteConcern(w="majority", j=True)).insert_one(document)
        except Exception as e:
            if self.not_master.search(e.__str__()):
                logger.warning("######## primary node not found ########")
                self.reconnect()
                self.insert(database, collection, document)
            else:
                logger.error("########## insert is not working due to {} #########".format(e))

    def find(self, database, collection, filter, **kwargs):
        return self.get_db(database).get_collection(collection).find_one(filter, **kwargs)

    def find_all(self, database, collection, filter, **kwargs):
        return self.get_db(database).get_collection(collection).find(filter, **kwargs)

    def update(self, database, collection, filter, update):
        try:
            return self.get_db(database).get_collection(collection).with_options(
                write_concern=WriteConcern(w="majority", j=True)).update_one(filter, update)

        except Exception as e:
            if self.not_master.search(e.__str__()):
                logger.warning("######## primary node not found ########")
                self.reconnect()
                self.update(database, collection, filter, update)
            else:
                logger.error("########## update is not working due to {} #########".format(e))
                ########## update is working due to not master #########

    def delete(self, database, collection, filter):
        return self.get_db(database).get_collection(collection).delete_one(filter)