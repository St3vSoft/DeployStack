#!/bin/bash
if [ -z "$PHYSICAL_VOLUME" ]; then
    if ! losetup {lvm_loop_dev} 2>/dev/null | grep -q '{lvm_image_file_path}'; then
        /sbin/losetup {lvm_loop_dev} {lvm_image_file_path}
    fi
fi
/sbin/vgchange -ay {VG_NAME}