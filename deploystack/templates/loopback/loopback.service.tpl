[Unit]
Description={description}
Before={before_services}
Wants={before_services}

After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes

ExecStart=/usr/bin/deploystack_loopback start {service} {backend_name}
ExecStop=/usr/bin/deploystack_loopback stop {service} {backend_name}

[Install]
WantedBy=multi-user.target