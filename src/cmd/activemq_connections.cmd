
eval [ activemq_connections_e ] = \
    my $username = '$USERNAME$' ? '--username=$USERNAME$' : q{}; \
    my $password = '$PASSWORD$' ? '--password=$PASSWORD$' : q{}; \
    my $ports = '$BROKER_PORTS$'; \
    if ( '$STOMP_PORT$' =~ '^\d{2,}$' ){\
        parse_lines('command [ STOMP ] = check_activemq_stomp -p $STOMP_PORT$ -H $HOSTADDRESS$ -D /queue/$QUEUEPREFIX$.stomp '."$username $password" ); }\
    if ( '$STOMP_SSL_PORT$' =~ '^\d{2,}$' ){\
        parse_lines('command [ STOMP_SSL ] = check_activemq_stomp -p $STOMP_SSL_PORT$ -s -C $HOSTCERT$ -K $HOSTKEY$ -H $HOSTADDRESS$ -D /queue/$QUEUEPREFIX$.stompssl' ); } \
    if ( '$OPENWIRE_PORT$' =~ '^\d{2,}$' ){\
        parse_lines('command [ OpenWire ] = check_activemq_openwire  -u tcp://$HOSTADDRESS$:$OPENWIRE_PORT$ -s $QUEUEPREFIX$.openwire '."$username $password"); } \
    if ( '$OPENWIRE_SSL_PORT$' =~ '^\d{2,}$' ){\
        parse_lines('command [ OpenWire_SSL ] = check_activemq_openwire  -u ssl://$HOSTADDRESS$:$OPENWIRE_SSL_PORT$ -s $QUEUEPREFIX$.openwiressl -K $KEYSTORE$ --keystoretype jks -T $TRUSTSTORE$ --keystorepwd $KEYSTOREPWD$'); }
