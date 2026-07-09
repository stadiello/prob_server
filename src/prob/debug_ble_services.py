import asyncio
from bleak import BleakScanner, BleakClient

UART_SERVICE_UUID = "e95d5400-251d-470a-a062-fa1922dfa9a8"

MIN_RSSI = -65


async def main():
    print("Scan BLE 10 secondes...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    candidates = []

    for device, adv in devices.values():
        rssi = adv.rssi
        name = device.name or adv.local_name or device.address

        if rssi is not None and rssi >= MIN_RSSI:
            candidates.append((rssi, name, device, adv))

    candidates.sort(reverse=True, key=lambda x: x[0])

    print("\nCandidats proches:")
    for rssi, name, device, adv in candidates:
        print(f"{rssi:4} dBm | {name:30} | {device.address}")

    print("\nTest des services GATT:")

    for rssi, name, device, adv in candidates:
        print(f"\n--- Test {name} | {device.address} | {rssi} dBm ---")

        try:
            async with BleakClient(device, timeout=20.0) as client:
                print("connecté")

                services = client.services

                found_uart = False

                for service in services:
                    print(" service:", service.uuid)

                    if service.uuid.lower() == UART_SERVICE_UUID:
                        found_uart = True

                    for char in service.characteristics:
                        props = ",".join(char.properties)
                        print("   char:", char.uuid, props)

                if found_uart:
                    print("\n✅ UART micro:bit trouvé ici !")
                    print("Adresse:", device.address)
                    return

        except Exception as e:
            print("échec:", type(e).__name__, e)

    print("\n❌ Aucun service UART trouvé.")


asyncio.run(main())
