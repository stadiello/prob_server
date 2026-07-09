/etc/systemd/system/microbit-ble-logger.service/etc/systemd/system/microbit-ble-logger.service

sudo systemctl start microbit-ble-logger.service

sudo systemctl start microbit-ble-logger.service
sudo systemctl status microbit-ble-logger.service

journalctl -u microbit-ble-logger.service -f
