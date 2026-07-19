[Unit]
Description={description}
Before={before_services} #cinder-volume.service tgt.service
DefaultDependencies=no
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=/etc/default/{service}-lvm
ExecStart=/usr/local/bin/{service}-loopback-start.sh
ExecStop=/usr/local/bin/{service}-loopback-stop.sh

[Install]
WantedBy=multi-user.target