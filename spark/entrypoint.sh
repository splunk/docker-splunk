#!/bin/sh

$SPARK_HOME/setenv.sh

if [ "x$SPLUNK_ROLE" = "xsplunk_spark_master" ]
then

    echo "Starting spark master"
    /opt/spark/sbin/start-master.sh

else

    echo "Starting spark worker"
    /opt/spark/sbin/start-slave.sh spark://$SPARK_MASTER_HOSTNAME:$SPARK_MASTER_PORT

fi
