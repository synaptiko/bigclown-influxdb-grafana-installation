# BigClown with InfluxDB and Grafana on Turris Omnia

Graphs of values gathered from BigClown sensors and nodes.

This setup uses Debian Stretch in LXC container on Turris Omnia.
InfluxDB is used as a DB, Grafana as a graph tool.

You first need to [setup the BigClown USB Dongle, Gateway and Mosquitto on Turris Omnia.](https://www.bigclown.com/doc/tutorials/custom-setup-on-turris/)

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
# wget https://dl.influxdata.com/influxdb/releases/influxdb_1.6.3_armhf.deb
# dpkg -i influxdb_1.6.3_armhf.deb
# chown influxdb:influxdb /var/lib/influxdb
# vim /etc/influxdb/influxdb.conf # uncomment or change following options
reporting-disabled = true
# systemctl daemon-reload
# systemctl enable influxdb
# systemctl start influxdb
```

### Install and configure ssh in the container

```
# lxc-attach -n influxdb-grafana # following commands are run in the LXC container context
# apt install ssh
# mkdir ~/.ssh
# vim ~/.ssh/authorized_keys # copy & paste your public key
```

### Install and configure Grafana
```
$ ssh root@grahps
# wget https://s3-us-west-2.amazonaws.com/grafana-releases/release/grafana_5.3.0-beta1_armhf.deb 
# apt install libfontconfig
# dpkg -i grafana_5.3.0-beta1_armhf.deb
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

*Hint: `gateway-ip` will be most probably 192.162.1.1 on Turris Omnia and I specified topic as bigclown-node.*

*This is a config I used:*
```
# uci show bc-gateway-usb-dongle
bc-gateway-usb-dongle.gateway=config
bc-gateway-usb-dongle.gateway.name='usb-dongle'
bc-gateway-usb-dongle.gateway.device='/dev/ttyUSB0'
bc-gateway-usb-dongle.gateway.automatic_rename_kit_nodes='1'
bc-gateway-usb-dongle.gateway.base_topic_prefix='bigclown-'
bc-gateway-usb-dongle.mqtt=config
bc-gateway-usb-dongle.mqtt.host='localhost'
bc-gateway-usb-dongle.mqtt.port='1883'
```

## Setup Caddy with HTTPS for the access from the Internet

Setup port forwarding of both 80 and 443 port to the IP of the lxc container.

SSH into lxc container:
```
$ ssh root@grahps
```

Download and extract [Caddy](https://caddyserver.com/download):
```
# wget "https://caddyserver.com/download/linux/arm7?license=personal&telemetry=off" -O caddy_v0.11.0_linux_arm7_personal.tar.gz
# tar -xzf caddy_v0.11.0_linux_arm7_personal.tar.gz caddy
```

Put the caddy binary in the system wide binary directory and give it
appropriate ownership and permissions:
```
# mv caddy /usr/local/bin
# chmod 755 /usr/local/bin/caddy
```

Give the caddy binary the ability to bind to privileged ports (e.g. 80, 443) as a non-root user:
```
# apt-get install libcap2-bin
# setcap 'cap_net_bind_service=+ep' /usr/local/bin/caddy
```

Set up the user, group, and directories that will be needed:
```
# groupadd -g 33 www-data
# useradd \
  -g www-data --no-user-group \
  --home-dir /var/www --no-create-home \
  --shell /usr/sbin/nologin \
  --system --uid 33 www-data
# mkdir /etc/caddy
# chown -R root:www-data /etc/caddy
```

Create and move Caddyfile:
```
# vim /etc/caddy/Caddyfile
graphs.yourdomain.com {
	basicauth / yourSecretUser yourSuperSecretPassword
	proxy / localhost:3000 {
		header_upstream -Authorization
	}
	gzip
	log stdout
	errors stderr
}

graphs:3000, graphs.lan:3000, <graphs-container-ip>:3000 {
	proxy / localhost:3000 {
		header_upstream -Authorization
	}
}
# chown www-data:www-data /etc/caddy/Caddyfile
# chmod 444 /etc/caddy/Caddyfile
```

Test the configuration & initialize certificates:
```
# ulimit -n 8192
# mkdir /etc/ssl/caddy
# chown root:www-data /etc/ssl/caddy
# chmod 0770 /etc/ssl/caddy
# CADDYPATH=/etc/ssl/caddy caddy -log stdout -agree=true -conf=/etc/caddy/Caddyfile -root=/var/tmp
> Enter your email address: <your@email.com><CR>
<C-c>
# chown -R root:www-data /etc/ssl/caddy
# chmod -R 0770 /etc/ssl/caddy
```

Create service file, start and enable it:
```
# vim /etc/systemd/system/caddy.service
[Unit]
Description=Caddy HTTP/2 web server
Documentation=https://caddyserver.com/docs
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service

[Service]
Restart=on-abnormal
User=www-data
Group=www-data
Environment=CADDYPATH=/etc/ssl/caddy
ExecStart=/usr/local/bin/caddy -log stdout -agree=true -conf=/etc/caddy/Caddyfile -root=/var/tmp
ExecReload=/bin/kill -USR1 $MAINPID
KillMode=mixed
KillSignal=SIGQUIT
TimeoutStopSec=5s
LimitNOFILE=1048576
LimitNPROC=512
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectSystem=full
ReadWriteDirectories=/etc/ssl/caddy
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
# chmod 644 /etc/systemd/system/caddy.service
# systemctl daemon-reload
# systemctl enable --now caddy.service
```

Verify everything is ok:
```
# journalctl --boot -u caddy.service
```
