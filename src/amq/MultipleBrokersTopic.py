#!/usr/bin/env python

# Massimo Paladin
# Massimo.Paladin@cern.ch

import os
from MultipleProducerConsumer import MultipleProducerConsumer, TimeoutException
import sys
import time
from utils.Timer import Timer

import logging
logging.basicConfig()
log = logging.getLogger(__file__)

class MultipleBrokersTopic(MultipleProducerConsumer):
    
    def __init__(self, mainBrokerName, mainBrokerHost, otherBrokers, port, destination='test.topic', hostcert=None, hostkey=None, messages=10, timeout=15):
        MultipleProducerConsumer.__init__(self)
        
        self.mainBrokerName = mainBrokerName
        self.mainBrokerHost = mainBrokerHost
        self.otherBrokers = otherBrokers
        self.port = port
        self.destination = destination
        self.hostcert = hostcert
        self.hostkey = hostkey
        self.messages = messages
        self.timeout = timeout
        
    def setup(self):
        self.destinationTopic = '/topic/%s' % self.destination
        
        if self.hostcert and self.hostkey:
            self.setSSLAuthentication(self.hostcert, self.hostkey)
        self.createBroker(self.mainBrokerName, self.mainBrokerHost, self.port)
        for name, host in self.otherBrokers.items():
            self.createBroker(name, host, self.port)
        
    def run(self):
        
        timer = Timer(self.timeout)
        
        ''' Starting consumers '''
        for name, host in self.otherBrokers.items():
            self.createConsumer(name, self.destinationTopic, timer.left)
        time.sleep(1)
        
        ''' Creating producer and sending messages '''
        self.createProducer(self.mainBrokerName, self.destinationTopic, timer.left)
        for i in range(self.messages):
            self.sendMessage(self.mainBrokerName, 
                             self.destinationTopic, 
                             {'persistent':'true'}, 
                             'testing-%s' % i)
        self.waitForMessagesToBeSent(self.mainBrokerName,
                                     self.destinationTopic,
                                     self.messages)
        
        for broker in self.otherBrokers:
            self.waitForMessagesToArrive(broker, self.destinationTopic, self.messages, timer.left)

        ''' Wait a couple of seconds to see if we get duplicated '''
        time.sleep(2)
        
        for broker in self.otherBrokers:
            self.assertMessagesNumber(broker, self.destinationTopic, self.messages)
            
    def stop(self):
        self.destroyAllBrokers()

if __name__ == '__main__':

    log.setLevel(logging.INFO)
    logging.getLogger('MultipleProducerConsumer').setLevel(logging.INFO)
    broker = 'vtb-27'
    brokerHost = 'vtb-generic-27'
    brokers = {'vtb-27':'vtb-generic-27', 
               'vtb-28':'vtb-generic-28',
               'vtb-33':'vtb-generic-33'}
#    broker = 'grid1'
#    brokerHost = 'gridmsg101.cern.ch'
#    brokers = {'grid1':'gridmsg101.cern.ch', 
#               'grid2':'gridmsg102.cern.ch',
#               'greece':'broker.afroditi.hellasgrid.gr',
#               'croatia':'msg.cro-ngi.hr'}

    mbt = MultipleBrokersTopic(broker, brokerHost, brokers, 6163)
    mbt.setup()
    
    try:
        mbt.start()
    except KeyboardInterrupt:
        print "keyboard interrupt"
    except TimeoutException, e:
        print '%s' % e
    except AssertionError, e:
        print '%s' % e
    mbt.stop()
     
    print 'Test passed!'
