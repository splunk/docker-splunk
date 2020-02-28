#!/bin/sh

MEM_TOTAL_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
MEM_TOTAL_BYTES=$(expr $MEM_TOTAL_KB \* 1024)
CGROUP_MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)

# use the lesser (cgroup memory limit, physical system memory)
if [ $MEM_TOTAL_BYTES -gt $CGROUP_MEMORY_LIMIT ]; then
    MEM_AVAILABLE=$CGROUP_MEMORY_LIMIT
else
    MEM_AVAILABLE=$MEM_TOTAL_BYTES
fi

# ensure 2Gb minimum
if [ $MEM_AVAILABLE -lt $(expr 2 \* 1024 \* 1024 \* 1024) ]; then
    echo "ERROR: minimum 2 Gi memory required"
    exit 1
fi

# reserve 1Gb for system
SPARK_WORKER_MEMORY=$(expr $MEM_AVAILABLE - 1024 \* 1024 \* 1024)

SYSTEM_CORES=$(nproc)
CGROUP_CPU_QUOTA=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
CGROUP_CPU_PERIOD=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
CGROUP_CPU_CORES=$(expr $CGROUP_CPU_QUOTA / $CGROUP_CPU_PERIOD)

# may be -1 if no cgroup limit is defined for the container
if [ "x$CGROUP_CPU_QUOTA" != "x-1" ]; then
    if [ $CGROUP_CPU_CORES -eq 0 ]; then
        # cpu is limited to fraction of a core
        SPARK_WORKER_CORES=1
    elif [ $CGROUP_CPU_CORES -gt $SYSTEM_CORES ]; then
        # limit is higher than physical number of cores
        SPARK_WORKER_CORES=$SYSTEM_CORES
    else
        # limit is less than or equal to physical number of cores
        SPARK_WORKER_CORES=$CGROUP_CPU_CORES
    fi
else
    SPARK_WORKER_CORES=$SYSTEM_CORES
fi

echo "export SPARK_PID_DIR=/opt/spark
export SPARK_WORKER_CORES=$SPARK_WORKER_CORES
export SPARK_WORKER_MEMORY=$SPARK_WORKER_MEMORY
export SPARK_DAEMON_MEMORY=1g
export SPARK_NO_DAEMONIZE=1
" >> /opt/spark/conf/spark-env.sh

echo "spark.eventLog.dir file:///opt/spark/eventlog
spark.history.fs.logDirectory file:///opt/spark/eventlog
" >> /opt/spark/conf/spark-defaults.conf

cat /opt/spark/conf/spark-env.sh
