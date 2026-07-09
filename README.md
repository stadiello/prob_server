scan_microbit_verbose.py
read_microbit_uart.py


/etc/systemd/system/microbit-ble-logger.service/etc/systemd/system/microbit-ble-logger.service

sudo systemctl start microbit-ble-logger.service

sudo systemctl start microbit-ble-logger.service
sudo systemctl status microbit-ble-logger.service

journalctl -u microbit-ble-logger.service -f
