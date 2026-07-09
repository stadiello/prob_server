import asyncio
from bleak import BleakScanner

MICROBIT_UART_SERVICE = "e95d5400-251d-470a-a062-fa1922dfa9a8"

async def main():
    print("Scan BLE pendant 15 secondes...")
    devices = await BleakScanner.discover(timeout=15, return_adv=True)

    found = []

    for address, (device, adv) in devices.items():
        name = device.name or adv.local_name or "UNKNOWN"
        rssi = adv.rssi
        service_uuids = [s.lower() for s in adv.service_uuids]

        is_microbit_uart = MICROBIT_UART_SERVICE in service_uuids

        found.append((rssi, name, address, service_uuids, is_microbit_uart))

    found.sort(reverse=True, key=lambda x: x[0])

    for rssi, name, address, services, is_microbit_uart in found:
        marker = " <-- MICROBIT UART ?" if is_microbit_uart else ""
        print(f"{rssi:4} dBm | {name:30} | {address}{marker}")

        if services:
            for s in services:
                print(f"          service: {s}")

asyncio.run(main())
