#! /bin/sh

### BEGIN INIT INFO
# Provides:          startup.py
### END INIT INFO

# If you want a command to always run, put it here

# Carry out specific functions when asked to by the system
case "$1" in
  start)
    echo "Starting collect_data.py"
    /home/pi/hamster/collect_data.py &
    ;;
  *)
    echo "Usage: /etc/init.d/startup.sh {start|stop}"
    exit 1
    ;;
esac

exit 0