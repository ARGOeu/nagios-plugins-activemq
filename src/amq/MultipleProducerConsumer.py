# Massimo Paladin
# Massimo.Paladin@cern.ch

import os
import socket
import stomp
import subprocess
import time
from collections import deque
from threading import Timer

import logging
logging.basicConfig()
log = logging.getLogger('MultipleProducerConsumer')

class TimeoutException(Exception):
    def __init__(self, cause):
        self._cause = cause
        
    def __str__(self):
        return '<Timeout exception: %s>' % self._cause
    
class ErrorFrameException(Exception):
    def __init__(self, cause):
        self._cause = cause
    
    def __str__(self):
        return '<Error frame exception: %s>' % self._cause
    
class Message(object):
    def __init__(self, headers, body):
        self._headers = headers
        self._body = body
    
    def headers(self):
        return self._headers
    
    def setHeaders(self, headers):
        self._headers = headers
    
    def body(self):
        return self._body
    
    def setBody(self, body):
        self._body = body
        
    headers = property(headers)
    body = property(body)
    
class RingBuffer(deque):
    def __init__(self, size):
        deque.__init__(self)
        self.size = size
        
    def full_append(self, item):
        deque.append(self, item)
        # full, pop the oldest item, left most item
        self.popleft()
        
    def append(self, item):
        deque.append(self, item)
        # max size reached, append becomes full_append
        if len(self) == self.size:
            self.append = self.full_append
    
    def get(self):
        """returns a list of size items (newest items)"""
        return list(self)

class Listener(object):
    
    def __init__(self, buffer_size=100):
        self._is_connected = False
        self._sent = RingBuffer(buffer_size)
        self._received = RingBuffer(buffer_size)
        self._errors = RingBuffer(buffer_size)
        self._waiting_receipt = dict()
        
    def getMessages(self):
        return self._received.get()
    
    def getWaitingForReceipt(self):
        return self._waiting_receipt
    
    def getErrors(self):
        return self._errors.get()
    
    def isConnected(self):
        return self._is_connected

    def on_connecting(self, host_and_port):
        log.debug('Connecting : %s:%s' % host_and_port)

    def on_connected(self, headers, body):
        self._is_connected = True
        self.__print_async("CONNECTED", headers, body)
    
    def on_disconnected(self, headers, body):
        self._is_connected = False
        self.__print_async("LOST CONNECTION", headers, body)

    def on_send(self, headers, body):
        if 'receipt' in headers:
            self._waiting_receipt[headers['receipt']] = Message(headers, body)
        else:
            self._sent.append(Message(headers, body))
        self.__print_async("SENT", headers, body)

    def on_message(self, headers, body):
        self._received.append(Message(headers, body))
        self.__print_async("MESSAGE", headers, body)

    def on_error(self, headers, body):
        self._errors.append(Message(headers, body))
        self.__print_async("ERROR", headers, body)
        raise ErrorFrameException('%s %s' % (headers, body))

    def on_receipt(self, headers, body):
        if headers.get('receipt-id', '') in self._waiting_receipt:
            self._sent.append(self._waiting_receipt[headers['receipt-id']])
            del self._waiting_receipt[headers['receipt-id']]
        self.__print_async("RECEIPT", headers, body)

    def __print_async(self, frame_type, headers, body):
        log.debug('Received : %s' % frame_type)
        
        if headers:
            for header_key in headers.keys():
                log.debug('Header   : %s: %s' %
                          (header_key, headers[header_key]))
        if body:            
            log.debug("body = '%s'" % body)
            
def connectionTimeout(connection):
    connection._Connection__running = False
            
class BrokerItem:
    
    def __init__(self, name, host, port, connection_extra_headers=None):
        self._name = name
        self._host = host
        self._port = port
        self._connection_extra_headers = connection_extra_headers
        self._consumers = list()
        self._producers = list()
        self._connections = dict()

    def name(self):
        return self._name
    name = property(name)
        
    def host(self):
        return self._host
    host = property(host)
    
    def port(self):
        return self._port
    port = property(port)
        
    def setConnectionExtraHeaders(self, connection_extra_headers):
        '''
            This method add extra_headers during connection time
        '''
        self._connection_extra_headers = connection_extra_headers
        
    def createConnection(self, destination, timeout):
        self._connections[destination] = stomp.Connection([(self._host, self._port)], **self._connection_extra_headers)
        self._connections[destination].set_listener('%s' % destination, Listener())
        # stomppy doesn't support connection timeout, resolving it with a timer
        stopper = Timer(timeout, connectionTimeout, [self._connections[destination]])
        stopper.start()
        self._connections[destination].start()
        stopper.cancel()
        if self._connections[destination].is_connected():
            self._connections[destination].connect()
        else:
            raise TimeoutException('Timeout during connection')
    
    def getConnection(self, destination):
        '''
        '''
        return self._connections.get(destination, None)
    
    def ensureConnection(self, destination, timeout):
        if destination not in self._connections:
            self.createConnection(destination, timeout)
        self.waitForConnection(destination, timeout)
            
    def closeConnection(self, destination):
        if ((destination in self._connections) and
            (destination not in self._consumers) and
            (destination not in self._producers)):
            self._connections[destination].stop()
            del self._connections[destination]
        
    def getListener(self, destination):
        if destination not in self._connections:
            return None
        return self._connections[destination].get_listener(destination)
        
    def createConsumer(self, destination, timeout=5):
        self.ensureConnection(destination, timeout)
        self._connections[destination].subscribe(destination=destination, ack='auto')
        if destination not in self._consumers:
            self._consumers.append(destination)
        
    def createProducer(self, destination, timeout=5):
        self.ensureConnection(destination, timeout)
        if destination not in self._producers:
            self._producers.append(destination)
            
    def waitForConnection(self, destination, timeout=5):
        '''
            Wait for established connection
        '''
        elapsed = 0
        while (not self.getListener(destination).isConnected()) \
                and (elapsed < timeout):
            elapsed += 0.1
            time.sleep(0.1)
        if not self.getListener(destination).isConnected():
            raise TimeoutException('timeout connecting to broker %s, waited for %.2f seconds' % (self._host, elapsed))
        
    def getMessages(self, destination):
        if self.getConnection(destination):
            return self.getConnection(destination).get_listener(destination).getMessages()
        return []
    
    def getErrors(self, destination):
        if self.getConnection(destination):
            return self.getConnection(destination).get_listener(destination).getErrors()
        return []
    
    def getWaitingForReceipt(self, destination):
        if self.getConnection(destination):
            return self.getConnection(destination).get_listener(destination).getWaitingForReceipt()
        return []
    
    def waitForMessagesToArrive(self, destination, number, timeout=5):
        '''
            Wait to receive a number of messages for given broker
            and destination with timeout
        '''
        elapsed = 0
        while (len(self.getMessages(destination)) < number) \
                and (elapsed < timeout):
            elapsed += 0.1
            time.sleep(0.1)
        if len(self.getMessages(destination)) < number:
            raise TimeoutException('timeout waiting for messages from broker %s and destination %s, waited for %.2f seconds' % (self._host, destination,elapsed))
        
    def waitForMessagesToBeSent(self, destination, timeout=5):
        '''
            Wait for all messages for given broker
            and destination to be sent with timeout
        '''
        elapsed = 0
        while (len(self.getWaitingForReceipt(destination)) > 0) \
                and (elapsed < timeout):
            elapsed += 0.1
            time.sleep(0.1)
        if len(self.getWaitingForReceipt(destination)) > 0:
            raise TimeoutException('timeout waiting for messages to be sent for broker %s and destination %s, waited for %.2f seconds' % (self._host, destination,elapsed))
        
    def sendMessage(self, destination, headers, body):
        if destination not in self._producers:
            self.createProducer(destination)
        self.getConnection(destination).send(body,
                                             destination=destination, 
                                             headers=headers)
    
    def deleteConsumer(self, destination):
        if destination in self._consumers:
            self._connections[destination].unsubscribe(destination=destination, ack='auto')
            self._consumers.remove(destination)
            self.closeConnection(destination)
        
    def deleteAllConsumers(self):
        for c in self._consumers:
            self.deleteConsumer(c)
        
    def deleteProducer(self, destination):
        if destination in self._producers:
            self._producers.remove(destination)
            self.closeConnection(destination)
        
    def deleteAllProducers(self):
        for p in self._producers:
            self.deleteProducer(p)
            
    def destroyConnection(self, connection):
        if self._connections[connection] and self._connections[connection].is_connected():
            self._connections[connection].stop()
            
    def destroyAllConnections(self):
        for t in self._connections:
            self.destroyConnection(t)
            
    def destroy(self):
        self.deleteAllConsumers()
        self.deleteAllProducers()
        self.destroyAllConnections()
        

class MultipleProducerConsumer:
    
    def __init__(self):
        self._connection_extra_headers = dict()
        self._consumers = dict()
        self._producers = dict()
        self._brokers = dict()
        
    def setSSLAuthentication(self, hostcert, hostkey):
        '''
            This method enable SSL authentication against the broker
        '''
        log.info('Setting ssl client certificate authentication:' + \
                 ('\n\tssl_cert_file: %s' % hostcert) + \
                 ('\n\tssl_key_file: %s' % hostkey))
        self._connection_extra_headers['use_ssl'] = True
        self._connection_extra_headers['ssl_cert_file'] = '%s' % hostcert
        self._connection_extra_headers['ssl_key_file'] = '%s' % hostkey
        
    def setConnectionExtraHeaders(self, key, value):
        '''
            Add an extra header to the connection headers for all brokers
        '''
        self._connection_extra_headers[key] = value
        
    def setConnectionHeader(self, brokerName, key, value):
        '''
            Add an extra header to the connection headers for a specified broker
        '''
        if brokerName not in self._brokers or key == None:
            return
        self._brokers[brokerName].setConnectionHeader(key, value)
        
    def createBroker(self, brokerName, host, port, extra_headers=dict()):
        '''
            Create Broker item
        '''
#        log.info('Creating broker session: (%s, %s, %d)' % (brokerName, host, port))
        self._brokers[brokerName] = BrokerItem(brokerName, host, port, dict(self._connection_extra_headers, **extra_headers))
        
    def createConsumer(self, brokerName, destination, timeout=5):
        '''
            Create and return a consumer for specified broker
        '''
        if brokerName in self._brokers:
            log.info('Creating consumer for %s on %s' % (brokerName, destination))
            return self._brokers[brokerName].createConsumer(destination, timeout)
        log.info('No broker with name %s' % brokerName)
        return None
    
    def createProducer(self, brokerName, destination, timeout=5):
        '''
            Create and return a producer for specified broker
        '''
        if brokerName in self._brokers:
            log.info('Creating producer for %s on %s' % (brokerName, destination))
            return self._brokers[brokerName].createProducer(destination, timeout=5)
        log.info('No broker with name %s' % brokerName)
        return None
    
    def waitForConnection(self, brokerName, destination, timeout=5):
        '''
            Wait for established connection
        '''
        if brokerName in self._brokers:
            log.info('Waiting for connection with %s' % (brokerName))
            return self._brokers[brokerName].waitForConnection(destination, timeout)
    
    def waitForMessagesToArrive(self, brokerName, destination, number, timeout=5):
        '''
            Wait to receive a number of messages for given broker
            and destination with timeout
        '''
        if brokerName in self._brokers:
            log.info('Waiting for %d messages from %s on broker %s' % (number, destination, brokerName))
            return self._brokers[brokerName].waitForMessagesToArrive(destination, number, timeout)
        
    def waitForMessagesToBeSent(self, brokerName, destination, timeout=5):
        '''
            Wait for all messages for given broker
            and destination to be sent with timeout
        '''
        if brokerName in self._brokers:
            log.info('Waiting for messages to be sent to %s on broker %s' % (destination, brokerName))
            return self._brokers[brokerName].waitForMessagesToBeSent(destination, timeout)
    
    def getMessages(self, brokerName, destination):
        '''
            Get all messages for selected broker and destination
        '''
        if brokerName in self._brokers:
            log.info('Messages received on %s in %s' % (destination, brokerName))
            return self._brokers[brokerName].getMessages(destination)
        log.info('No broker with name %s' % brokerName)
        return []
    
    def getErrors(self, brokerName, destination):
        '''
            Get all errors for selected broker and destination
        '''
        if brokerName in self._brokers:
            log.info('Error frames received on %s in %s' % (destination, brokerName))
            return self._brokers[brokerName].getErrors(destination)
        log.info('No broker with name %s' % brokerName)
        return []
    
    def assertMessagesNumber(self, brokerName, destination, number):
        '''
            Assert that we received a certain number of messages for given broker and destination
        '''
        if brokerName in self._brokers:
            received = len(self.getMessages(brokerName, destination))
            assert number == received, ('Received %s messages instead of %s on %s in broker %s:%d' \
                                        % (received, number, destination, self._brokers[brokerName].host, self._brokers[brokerName].port))
        else:
            assert 0==1 , ('Broker session not established')
    
    def sendMessage(self, brokerName, destination, headers, body):
        '''
            Send a message to the selected broker and destination
        '''
        if brokerName in self._brokers:
            log.info('Sending message to %s on broker %s' % (destination, brokerName))
            self._brokers[brokerName].sendMessage(destination,
                                                  headers, 
                                                  body)
            return True
        log.info('No broker with name %s' % brokerName)
        return False
    
    def destroyAllBrokers(self):
        '''
            Delete all broker items
        '''
        for b in self._brokers:
            self._brokers[b].destroy()
    
    def destroyBroker(self, brokerName):
        '''
            Delete a broker
        '''
        if brokerName in self._brokers:
            log.info('Deleting session with broker %s' % (brokerName))
            self._brokers[brokerName].destroy()
    
    def deleteProducer(self, brokerName, destination):
        '''
            Delete a producer for the selected broker
        '''
        if brokerName in self._brokers:
            log.info('Deleting producer for %s on %s' % (destination, brokerName))
            self._brokers[brokerName].deleteProducer(destination)
        
    def deleteAllProducers(self, brokerName):
        '''
            Delete all the producers for the selected broker
        '''
        if brokerName in self._brokers:
            self._brokers[brokerName].deleteAllProducers()
            
    def deleteConsumer(self, brokerName, destination):
        '''
            Delete a consumer for the selected broker
        '''
        if brokerName in self._brokers:
            log.info('Deleting consumer for %s on %s' % (destination, brokerName))
            self._brokers[brokerName].deleteConsumer(destination)
        
    def deleteAllConsumers(self, brokerName):
        '''
            Delete all the consumers for the selected broker
        '''
        if brokerName in self._brokers:
            self._brokers[brokerName].deleteAllConsumers()
            
    def printMessage(self, message, headers=False):
        '''
            Printing a message
        '''
        if headers:
            for header_key, header_value in message.headers().items():
                print 'Header   : %s: %s' % (header_key, header_value)
        print 'Body: \n%s' % message.body()
        
    def printMessages(self, messages, headers=False):
        '''
            Printing a list of messages
        '''
        for message in messages:
            self.printMessage(message, headers)
            
    def setup(self):
        '''
            Setup the environment
        '''
        pass

    def run(self):
        '''
            Method invoked by the start action 
        '''
        pass
    
    def start(self):
        '''
            start action
        '''
        self.run()
    
    def stop(self):
        '''
            stop action
        '''
        self.destroyAllBrokers()
    
