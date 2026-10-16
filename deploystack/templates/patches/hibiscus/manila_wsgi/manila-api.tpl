Listen 8786

<VirtualHost *:8786>
    WSGIScriptAlias / /usr/lib/python3/dist-packages/manila/wsgi/api.py
    WSGIDaemonProcess manila-api processes=5 threads=1 user=manila group=manila display-name=%{GROUP}
    WSGIProcessGroup manila-api
    WSGIApplicationGroup %{GLOBAL}
    WSGIPassAuthorization On

    <IfVersion >= 2.4>
      ErrorLogFormat "%{cu}t %M"
    </IfVersion>

    ErrorLog /var/log/apache2/manila_api_error.log
    CustomLog /var/log/apache2/manila_api_access.log combined

    <Directory /usr/lib/python3/dist-packages/manila/wsgi>
        <IfVersion >= 2.4>
            Require all granted
        </IfVersion>
        <IfVersion < 2.4>
            Order allow,deny
            Allow from all
        </IfVersion>
    </Directory>
</VirtualHost>
