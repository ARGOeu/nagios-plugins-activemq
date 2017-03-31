package org.activemq.probes;
/**
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import java.io.File;
import java.io.IOException;
import java.util.Arrays;

import javax.jms.Connection;
import javax.jms.DeliveryMode;
import javax.jms.Destination;
import javax.jms.ExceptionListener;
import javax.jms.JMSException;
import javax.jms.Message;
import javax.jms.MessageConsumer;
import javax.jms.MessageListener;
import javax.jms.MessageProducer;
import javax.jms.Session;
import javax.jms.TextMessage;
import javax.jms.Topic;

import org.apache.activemq.ActiveMQConnection;
import org.apache.activemq.ActiveMQConnectionFactory;
import org.apache.activemq.util.IndentPrinter;


/*
 * /usr/bin/java -classpath ".:/opt/activemq/lib/*:/opt/nagios/plugins/openwire" OpenWireProbe  --url=ssl://vtb-generic-16:6167 --subject="testopenwiressl" --ks=/etc/mycerts/mycert.ks --kstype="jks" --ts="/etc/mycerts/broker.ts" --kspwd="password"
 * /usr/bin/java -classpath ".:/opt/activemq/lib/*:/opt/nagios/plugins/openwire" OpenWireProbe  --url=tcp://vtb-generic-16:6166 --subject="testopenwire"
 */

public class OpenWireProbe implements MessageListener, ExceptionListener {
    public static int NAGIOS_OK = 0;
    public static int NAGIOS_WARNING = 1;
    public static int NAGIOS_CRITICAL = 2;
    public static int NAGIOS_UNKNOWN = 3;

    private boolean running;

    private Session session;
    private Destination destination;
    private MessageProducer replyProducer;

    private boolean ssldebug = false;
    private boolean verbose = false;
    private String subject = "nagiosopenwire";
    private boolean topic;
    private String url = ActiveMQConnection.DEFAULT_BROKER_URL;
    private boolean transacted;
    private boolean durable;
    private String consumerName = "nagioscheck";
    private int ackMode = Session.AUTO_ACKNOWLEDGE;
    private long receiveTimeOut = 1000;
    private long timeToLive;
    private boolean persistent;
    private String ts = "";
    private String tsPwd = "";
    private String tsType = "jks"; // pkcs12
    private String ks = "";
    private String ksPwd = "";
    private String ksType = "jks"; // pkcs12
    private String username = null;
    private String password = null;
    
    private boolean sent = false;
    private boolean received = false;
    private int returnCode = NAGIOS_UNKNOWN;
    
    private Connection connection = null;

    public static void main(String[] args) {
        OpenWireProbe prober = new OpenWireProbe();
        String[] unknown = CommandLineSupport.setOptions(prober, args);
        if (unknown.length > 0) {
            System.out.println("UNKNOWN - options: " + Arrays.toString(unknown));
            System.exit(NAGIOS_UNKNOWN);
        }
        prober.run();
    }
    

    public void run() {
        try {
            running = true;

            setSslEnv();
            
            ActiveMQConnectionFactory connectionFactory = new ActiveMQConnectionFactory(url);
            connection = connectionFactory.createConnection(username, password);
            connection.setExceptionListener(this);
            connection.start();

            session = connection.createSession(transacted, ackMode);
            if (topic) {
                destination = session.createTopic(subject);
            } else {
                destination = session.createQueue(subject);
            }

            replyProducer = session.createProducer(null);
            replyProducer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
            
            // Create the producer.
            MessageProducer producer = session.createProducer(destination);
            if (persistent) {
                producer.setDeliveryMode(DeliveryMode.PERSISTENT);
            } else {
                producer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
            }
            if (timeToLive != 0) {
                producer.setTimeToLive(timeToLive);
            }

            // Start sending messages
            sendMessage(session, producer);

            if (verbose) {
            	System.out.println("Done.");
            
		        // Use the ActiveMQConnection interface to dump the connection
		        // stats.
		        ActiveMQConnection c = (ActiveMQConnection)connection;
		        c.getConnectionStats().dump(new IndentPrinter());
		        
            }

            MessageConsumer consumer = null;
            if (durable && topic) {
                consumer = session.createDurableSubscriber((Topic)destination, consumerName);
            } else {
                consumer = session.createConsumer(destination);
            }

            if (receiveTimeOut == 0) {
                consumer.setMessageListener(this);
            } else {
                consumeMessagesAndClose(connection, session, consumer, receiveTimeOut);
            }
            
            if(received && sent){
            	System.out.println("connection works: sent and received 1 messages");
            	returnCode = NAGIOS_OK;
            }else if(sent){
            	System.out.println("sent 1 message, received 0 messages");
            	returnCode = NAGIOS_WARNING;
            }else{
            	System.out.println("sent and received 0 messages");
            	returnCode = NAGIOS_CRITICAL;
            }

        } catch (JMSException e) {
        	System.out.println("" + e);
            if(verbose) e.printStackTrace();
            returnCode = NAGIOS_CRITICAL;
        } catch (Exception e) {
            System.out.println("" + e);
            if(verbose) e.printStackTrace();
            returnCode = NAGIOS_CRITICAL;
        } finally {
            try {
                connection.close();
            } catch (Throwable ignore) {
            }
        }
        System.exit(returnCode);
    }


	private void setSslEnv() {
		if(ts != ""){
			
			if(!fileExists(ts)){
				System.out.println("TrustStore file doesn't exists or not readable");
				System.exit(NAGIOS_UNKNOWN);
			}
			if(!fileExists(ks)){
				System.out.println("KeyStore file doesn't exists or not readable");
				System.exit(NAGIOS_UNKNOWN);
			}
			
			if(ssldebug) System.setProperty("javax.net.debug", "ssl");
			
			System.setProperty("javax.net.ssl.trustStoreType", tsType);
			System.setProperty("javax.net.ssl.trustStore", ts);
			System.setProperty("javax.net.ssl.trustStorePassword", tsPwd);

			System.setProperty("javax.net.ssl.keyStoreType", ksType);
			System.setProperty("javax.net.ssl.keyStore", ks);
			System.setProperty("javax.net.ssl.keyStorePassword", ksPwd);
		}
	}
    
    protected boolean fileExists(String path){
    	File f = new File(path);
    	return f.exists() && f.canRead() && f.isFile();
    }
    
    protected void sendMessage(Session session, MessageProducer producer) throws Exception {

        TextMessage message = session.createTextMessage("OpenWire connection testing!");

        if (verbose) System.out.println("Sending message: " + message.getText());

        producer.send(message);
        sent = true;
        if (transacted) {
            session.commit();
        }

    }

    public void onMessage(Message message) {
        try {

            if (message instanceof TextMessage) {
                TextMessage txtMsg = (TextMessage)message;
                received = true;
                if (verbose) {
                    System.out.println("Received: " + txtMsg.getText());
                }
            } else {
                if (verbose) {
                    System.out.println("Received: " + message);
                }
            }

            if (message.getJMSReplyTo() != null) {
                replyProducer.send(message.getJMSReplyTo(), session.createTextMessage("Reply: " + message.getJMSMessageID()));
            }

            if (transacted) {
                session.commit();
            } else if (ackMode == Session.CLIENT_ACKNOWLEDGE) {
                message.acknowledge();
            }

        } catch (JMSException e) {
        	System.out.println("CRITICAL: " + e);
            System.out.println("Caught: " + e);
            e.printStackTrace();
            System.exit(NAGIOS_CRITICAL);
        }
    }

    public synchronized void onException(JMSException ex) {
        System.out.println("CRITICAL - JMS Exception occured.  Shutting down client.");
        returnCode = NAGIOS_CRITICAL;
        running = false;
    }

    synchronized boolean isRunning() {
        return running;
    }

    protected void consumeMessagesAndClose(Connection connection, Session session, MessageConsumer consumer, long timeout) throws JMSException, IOException {
    	if (verbose) {
    		System.out.println("We will consume messages while they continue to be delivered within: " + timeout + " ms, and then we will shutdown");
    	}
    		
        Message message;
        while (!received && (message = consumer.receive(timeout)) != null) {
            onMessage(message);
        }

        if (verbose) {
        	System.out.println("Closing connection");
        }
        consumer.close();
        session.close();
        connection.close();
        
    }

    public void setAckMode(String ackMode) {
        if ("CLIENT_ACKNOWLEDGE".equals(ackMode)) {
            this.ackMode = Session.CLIENT_ACKNOWLEDGE;
        }
        if ("AUTO_ACKNOWLEDGE".equals(ackMode)) {
            this.ackMode = Session.AUTO_ACKNOWLEDGE;
        }
        if ("DUPS_OK_ACKNOWLEDGE".equals(ackMode)) {
            this.ackMode = Session.DUPS_OK_ACKNOWLEDGE;
        }
        if ("SESSION_TRANSACTED".equals(ackMode)) {
            this.ackMode = Session.SESSION_TRANSACTED;
        }
    }

    public void setReceiveTimeOut(long receiveTimeOut) {
        this.receiveTimeOut = receiveTimeOut;
    }

    public void setSubject(String subject) {
        this.subject = subject;
    }
    
    public void setTs(String ts) {
        this.ts = ts;
    }
    
    public void setTspwd(String tsPwd) {
        this.tsPwd = tsPwd;
    }
    
    public void setTstype(String tsType) {
        this.tsType = tsType;
    }
    
    public void setKs(String ks) {
        this.ks = ks;
    }
    
    public void setKspwd(String ksPwd) {
        this.ksPwd = ksPwd;
    }
    
    public void setKstype(String ksType) {
        this.ksType = ksType;
    }

    public void setSsldebug(boolean ssldebug) {
        this.ssldebug = ssldebug;
    }
    
    public void setTopic(boolean topic) {
        this.topic = topic;
    }

    public void setQueue(boolean queue) {
        this.topic = !queue;
    }

    public void setTransacted(boolean transacted) {
        this.transacted = transacted;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public void setVerbose(boolean verbose) {
        this.verbose = verbose;
    }
    
    public void setPersistent(boolean durable) {
        this.persistent = durable;
    }

    public void setTimeToLive(long timeToLive) {
        this.timeToLive = timeToLive;
    }
    
    public String getUsername() {
		return username;
	}

	public void setUsername(String username) {
		this.username = username;
	}

	public String getPassword() {
		return password;
	}

	public void setPassword(String password) {
		this.password = password;
	}
}
