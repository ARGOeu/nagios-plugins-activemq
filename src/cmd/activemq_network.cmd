
eval [ msg_brokers_e ] = \
	my $credentials = '$CREDENTIALS$' !~ /^\$CREDENTIALS\$$/ ? '--credentials=$CREDENTIALS$' : q{}; \
	if ('$MSGBROKERS$' !~ /^\$MSGBROKERS\$$/) { \
		parse_lines('command [ msg_brokers ] = msg-brokers find --bdii $BDIIHOST$ --cache /var/cache/org.activemq.probes/$HOSTNAME$.msg-brokers.list && echo OK'); \
	} \
        my $dest_prefix = '$DESTPREFIX$' =~ '^\$DESTPREFIX\$$' ? 'global.monitor.test.' : '$DESTPREFIX$'; \
	my $sslopts = '$HOSTCERT$' !~ /^\$HOSTCERT\$$/ && '$HOSTKEY$' !~ /^\$HOSTKEY\$$/ ? '-C $HOSTCERT$ -K $HOSTKEY$' : q{}; \
	my $port = '$PORT$' !~ /^\$PORT\$$/ ? '$PORT$' : '6162'; \
    parse_lines("command [ Topic_Network ] = check_activemq_network -p $port -s $sslopts -H $HOSTNAME$ -D " . $dest_prefix . "topicnetwork.$HOSTNAME$ -F /var/cache/org.activemq.probes/$HOSTNAME$.msg-brokers.list -m 1 $credentials" ); \
    parse_lines("command [ Virtual_Destinations_Network ] = check_activemq_network -p $port -s $sslopts -H $HOSTNAME$ -D " . $dest_prefix . "virtualdestinations.$HOSTNAME$ -F /var/cache/org.activemq.probes/$HOSTNAME$.msg-brokers.list -m 1 -T $credentials" );
