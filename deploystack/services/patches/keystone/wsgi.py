import re
from pathlib import Path

apache_wsgi_conf_path = "/etc/apache2/sites-enabled/keystone.conf"

def replace_if_exists(path: str, old: str, new: str) -> bool:
    p = Path(path)
    content = p.read_text()

    if old not in content:
        return False

    p.write_text(content.replace(old, new))
    return True

def patch_keystone_wsgi():
    path = apache_wsgi_conf_path
    changed = False

    if replace_if_exists(
        path,
        "WSGIScriptAlias / /usr/bin/keystone-wsgi-public",
        "WSGIScriptAlias / /usr/lib/python3/dist-packages/keystone/wsgi/api.py",
    ):
        changed = True

    content = Path(path).read_text()

    directory_pattern = re.compile(
        r"<Directory\s+/usr/lib/python3/dist-packages/keystone/wsgi\s*>"
        r"\s*Require\s+all\s+granted\s*"
        r"</Directory>",
        re.MULTILINE,
    )

    if not directory_pattern.search(content):
        directory_block = """\
    <Directory /usr/lib/python3/dist-packages/keystone/wsgi>
        Require all granted
    </Directory>
"""

        content = re.sub(
            r"(\s*WSGIPassAuthorization\s+On\s*)",
            r"\1\n" + directory_block,
            content,
            count=1,
        )

        Path(path).write_text(content)
        changed = True

    return changed
