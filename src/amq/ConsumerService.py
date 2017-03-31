#!/usr/bin/env python

# Massimo Paladin
# Massimo.Paladin@cern.ch

import commands
import os
import time
from MultipleProducerConsumer import MultipleProducerConsumer, TimeoutException
from utils.Timer import Timer

import logging
logging.basicConfig()
log = logging.getLogger("ConsumerService")

MONITOR_TEST_HEADER = 'monitor.test'
MONITOR_TEST_TIME_HEADER = MONITOR_TEST_HEADER + '.timestamp'
MONITOR_TEST_SERVERID = MONITOR_TEST_HEADER + '.serverid'
MONITOR_TEST_CLIENTNAME = MONITOR_TEST_HEADER + '.clientname'
MONITOR_EXPIRY_TIME = 86400 * 1000 # 1 Day

def uuidgen():
    return commands.getoutput('uuidgen')

class ConsumerServiceSender(MultipleProducerConsumer):
    
    def __init__(self, brokerName, brokerHost, 
                 destclientname='consumerService',
                 destination='/queue/monitor.test.consumerService',
                 hostcert=None, 
                 hostkey=None,
                 logfile='/tmp/monitor.test.consumerService_dev',
                 port=6163, 
                 replyto='/queue/monitor.test.consumerService', 
                 serverid='opsmonitor_dev',
                 timeout=15,
                 **opts):
        MultipleProducerConsumer.__init__(self)
        
        self.brokerName = brokerName
        self.brokerHost = brokerHost
        self.destclientname = destclientname
        self.destination = destination
        self.hostcert = hostcert
        self.hostkey = hostkey
        self.logfile = logfile
        self.port = port
        self.replyto = replyto
        self.serverid = serverid
        self.timeout = timeout
        
    def setup(self):
        
        if self.hostcert and self.hostkey:
            self.setSSLAuthentication(self.hostcert, self.hostkey)
        self.createBroker(self.brokerName, self.brokerHost, self.port)
        
    def run(self):
        
        timer = Timer(self.timeout)
        
        ''' Creating producer and sending a message '''
        self.createProducer(self.brokerName, self.destination, timer.left)
        seq_id = uuidgen()
        sending_time = timer.time()
        self.sendMessage(self.brokerName, 
                         self.destination, 
                         { 'expires': int(sending_time * 1000 + 
                                        MONITOR_EXPIRY_TIME),
                            'persistent':'true',
                            'receipt' : 'consumer_service_%s' % seq_id,
                            'reply-to':'%s' % self.replyto, 
                            MONITOR_TEST_CLIENTNAME:'%s' % self.destclientname,
                            MONITOR_TEST_SERVERID:'%s' % self.serverid,
                            MONITOR_TEST_HEADER:'%s' % seq_id,
                            MONITOR_TEST_TIME_HEADER:'%f' % sending_time }, 
                         'testing consumer service!')
        self.waitForMessagesToBeSent(self.brokerName,
                                     self.destination,
                                     timer.left)
        
        try:
            if os.path.exists(self.logfile):
                f = open(self.logfile, 'a')
            else:
                f = open(self.logfile, 'w')
        except IOError:
            raise IOError("Error opening log file")
        f.write('%f %s\n' % (sending_time, seq_id))
        f.close()
             
class ConsumerServiceReceiver(MultipleProducerConsumer):
    
    def __init__(self, brokerName, brokerHost, 
                 critical=60,
                 destclientname='consumerService',
                 destination='/queue/monitor.test.consumerService',
                 hostcert=None, 
                 hostkey=None,
                 logfile='/tmp/monitor.test.consumerService_dev',
                 port=6163, 
                 serverid='opsmonitor_dev',
                 timeout=15,
                 warning=30,
                 **opts):
        MultipleProducerConsumer.__init__(self)
        
        self.brokerName = brokerName
        self.brokerHost = brokerHost
        self.critical = critical
        self.destclientname = destclientname
        self.destination = destination
        self.hostcert = hostcert
        self.hostkey = hostkey
        self.logfile = logfile
        self.port = port
        self.serverid = serverid
        self.timeout = timeout
        self.warning = warning
        
        self.avgDelay = None
        self.results = dict()
        
    def getAvgDelay(self):
        return self.avgDelay
    avgDelay = property(getAvgDelay)
    
    def getResults(self):
        return self.results
    results = property(getResults)
        
    def setup(self):
        
        if self.hostcert and self.hostkey:
            self.setSSLAuthentication(self.hostcert, self.hostkey)
        self.createBroker(self.brokerName, self.brokerHost, self.port)
        
    def run(self):
        
        timer = Timer(self.timeout)
        
        ''' Starting consumer '''
        self.createConsumer(self.brokerName, self.destination, timer.left)
        timer.sleep(2)
        
        ''' Getting received messages '''
        messages = self.getMessages(self.brokerName, self.destination)
        self.received = self.filterMessages(messages)
        self.results['received'] = len(self.received)
        self.readLog()
        self.writeNewLog()
        
        
    def readLog(self):
        ''' Read logged values and look for the youngest value received that appear in the logfile '''
        try:
            f = open(self.logfile, 'r')
        except IOError:
            raise IOError("Error opening log file")
        
        delays = []
        self.logged = dict()
        self.youngestLogged = 0
        log.debug('received: %s' % self.received)
        for line in f:
            l = [v.strip() for v in line.split(' ')]
            if l and len(l) == 2:
                self.logged[l[1]] = float(l[0])
                if (l[1] in self.received):
                    log.debug('timing: %2f %2f' % (float(self.logged[l[1]]), self.received[l[1]]))
                    delays.append( max( 
                            self.received[l[1]] - float(self.logged[l[1]]), 0.0 ) )
                    if (self.logged[l[1]] > self.youngestLogged):
                        self.youngestLogged = self.logged[l[1]]
                log.debug('%d %s' % (self.logged[l[1]], l[1]))
        f.close()
        log.debug('youngest message received: %s' % self.youngestLogged)
        if delays:
            self.avgDelay = sum(delays, 0.0) / len(delays)
        
    def writeNewLog(self):
        ''' 
        Rewrite logfile without the received and the old values, 
        checking age of non-received messages 
        '''
        try:
            f = open(self.logfile, 'w')
        except IOError:
            raise IOError("Error opening log file")
        
        self.results['old'] = 0
        self.results['warning'] = 0
        self.results['critical'] = 0
        now = time.time()
        for k, val in self.logged.items():
            if val < self.youngestLogged and k not in self.received:
                self.results['old'] += 1
            elif val > self.youngestLogged:
                ''' Check age and increase number of warning and critical values '''
                if (now - val) > (self.warning * 60):
                    self.results['warning'] += 1
                elif  (now - val) > (self.critical * 60):
                    self.results['critical'] += 1
                ''' Rewrite value in logfile '''
                f.write('%f %s\n' % (val, k))
                log.debug('Writing %d %s' % (val, k))
        f.close()
        
    def filterMessages(self, messages):
        nms = dict()
        for msg in messages:
            headers = msg.headers
            if MONITOR_TEST_HEADER in headers \
                 and headers.get(MONITOR_TEST_CLIENTNAME, '') == self.destclientname \
                 and headers.get(MONITOR_TEST_SERVERID, '') == self.serverid:
               nms[headers[MONITOR_TEST_HEADER].strip()] = \
                    float(headers.get(MONITOR_TEST_TIME_HEADER, 0))
        return nms
            
if __name__ == '__main__':

    log.setLevel(logging.INFO)
    logging.getLogger('MultipleProducerConsumer').setLevel(logging.INFO)
    broker = 'vtb26'
    brokerHost = 'vtb-generic-26.cern.ch'

    mcs = ConsumerServiceSender(broker, brokerHost, port=6163)
    mcs.setup()
    try:
        mcs.start()
    except IOError, e:
        print '%s' % e
    except KeyboardInterrupt:
        print "keyboard interrupt"
    except TimeoutException, e:
        print '%s' % e
    mcs.stop()
    
    mcr = ConsumerServiceReceiver(broker, brokerHost, port=6163)
    mcr.setup()
    try:
        mcr.start()
    except IOError, e:
        print '%s' % e
    except KeyboardInterrupt:
        print "keyboard interrupt"
    except TimeoutException, e:
        print '%s' % e
    mcr.stop()
    
    print 'Test passed!'
