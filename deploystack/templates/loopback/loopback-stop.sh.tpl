#!/bin/bash
/sbin/vgchange -an {VG_NAME}
if [ -z "$PHYSICAL_VOLUME" ]; then
    if losetup {lvm_loop_dev} 2>/dev/null | grep -q '{lvm_image_file_path}'; then
        /sbin/losetup -d {lvm_loop_dev}
    fi
fi