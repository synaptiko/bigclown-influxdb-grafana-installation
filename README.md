# BigClown with InfluxDB and Grafana on Turris Omnia

Graphs of values gathered from BigClown sensors and nodes.

This setup uses Debian Stretch in LXC container on Turris Omnia.
InfluxDB is used as a DB, Grafana as a graph tool.

You first need to [setup the BigClown USB Dongle, Gateway and Mosquitto on Turris Omnia.](https://www.bigclown.com/doc/tutorials/turris-installation/)

*Note: the procedure was derived from [`bigclownlabs/bc-raspbian`](https://github.com/bigclownlabs/bc-raspbian).*

## Create LXC container

Commands below assumes three things:
- `/mnt/data` exists and it's mount to the mSata SSD disk on Turris Omnia
- `/mnt/data/{influxdb,grafana}` exists; just run `mkdir /mnt/data/{influxdb,grafana}` if not
- `/srv/lxc` is mount to `/mnt/data/lxc`; just put this line into `/etc/rc.local`: `mount --bind /mnt/data/lxc /srv/lxc`

### Create and configure new container

```
$ ssh root@<omnia>
# lxc-create -t download -n influxdb-grafana
Distribution: Debian
Release: Stretch
Architecture: armv7l
# vim /srv/lxc/influxdb-grafana/config # add the following line =>
lxc.mount.entry=/mnt/data/influxdb var/lib/influxdb none bind,create=dir 0 0
lxc.mount.entry=/mnt/data/grafana var/lib/grafana none bind,create=dir 0 0
# vim /etc/config/lxc-auto # add the following line =>
config container
	option name influxdb-grafana
	option timeout 60
```

### Configure the system in the container

```
# lxc-attach -n influxdb-grafana # following commands are run in the LXC container context
# apt update
# apt upgrade
# apt install vim
# vim /etc/hostname
graphs
# vim /etc/dhcp/dhclient.conf # remove `host-name` key from request configuration
…
request subnet-mask, broadcast-address, time-offset, routers,
	domain-name, domain-name-servers, domain-search,
…
# dpkg-reconfigure tzdata # set correct timezone, ie. 'Europe/Prague'
```

### Install and configure InfluxDB

```
# lxc-attach -n influxdb-grafana # following commands are run in the LXC container context
# apt install wget
# wget https://dl.influxdata.com/influxdb/releases/influxdb_1.4.2_armhf.deb
# dpkg -i influxdb_1.4.2_armhf.deb
# chown influxdb:influxdb /var/lib/influxdb
# systemctl daemon-reload
# systemctl enable influxdb
# systemctl start influxdb
# vim /etc/influxdb/influxdb.conf # uncomment or change following options
reporting-disabled = true
```

### Install and configure ssh in the container

```
# lxc-attach -n influxdb-grafana # following commands are run in the LXC container context
# apt install ssh
# mkdir ~/.ssh
# vim ~/.ssh/authorized_keys # copy & paste your public key
```

### Install and configure Grafana

Follow the steps in [`grafana-on-raspberry/ci/README.md`](https://github.com/fg2it/grafana-on-raspberry/tree/master/ci#usage) to get armv7 installation `.deb` file.

Copy the `.deb` file into your LXC container, eg.:
```
$ scp grafana_5.0.0-1514129671pre1_armhf.deb root@graphs:grafana_5.0.0-1514129671pre1_armhf.deb
$ ssh root@grahps
# apt install libfontconfig
# dpkg -i grafana_5.0.0-1514129671pre1_armhf.deb
# chown grafana:grafana /var/lib/grafana
# systemctl daemon-reload
# systemctl enable grafana-server
# systemctl start grafana-server
```

### Install and configure BigClown to Mosquitto script

*Note: scripts were derived from [`blavka/bcp-monitor-in-docker`](https://github.com/blavka/bcp-monitor-in-docker).*

```
$ ssh root@grahps
# addgroup --system bigclown --quiet
# adduser --system --no-create-home --ingroup bigclown --disabled-password --shell /bin/false bigclown
# apt install python3-pip mosquitto-clients
# pip3 install influxdb docopt paho-mqtt
# wget https://raw.githubusercontent.com/synaptiko/bigclown-influxdb-grafana-installation/master/bc-mqtt-to-influxdb.py -O /usr/bin/bc-mqtt-to-influxdb
# chmod +x /usr/bin/bc-mqtt-to-influxdb
# wget https://raw.githubusercontent.com/synaptiko/bigclown-influxdb-grafana-installation/master/bc-mqtt-to-influxdb.service -O /etc/systemd/system/bc-mqtt-to-influxdb.service
# vim /etc/systemd/system/bc-mqtt-to-influxdb.service # update command arguments accordingly (or leave as is)
ExecStart=/usr/bin/bc-mqtt-to-influxdb -h <gateway-ip> -t <base-topic>
# systemctl daemon-reload
# systemctl enable bc-mqtt-to-influxdb
# systemctl start bc-mqtt-to-influxdb
```
