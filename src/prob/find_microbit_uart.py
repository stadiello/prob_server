import asyncio
from bleak import BleakScanner, BleakClient

MICROBIT_UART_SERVICE = "e95d5400-251d-470a-a062-fa1922dfa9a8"

IGNORE_NAMES = {
    "toshiba",
}

async def try_device(address, name, rssi):
    print(f"\nTest {address} | {name} | {rssi} dBm")

    try:
        async with BleakClient(address, timeout=8) as client:
            print("  connecté")

            services = client.services

            for service in services:
                service_uuid = service.uuid.lower()

                if service_uuid == MICROBIT_UART_SERVICE:
                    print("  ✅ MICRO:BIT UART TROUVÉ")
                    print(f"  Adresse: {address}")
                    return True

                for char in service.characteristics:
                    if char.uuid.lower().startswith("e95d"):
                        print("  UUID micro:bit trouvé:", char.uuid)

            print("  pas de service UART micro:bit")
            return False

    except Exception as e:
        print("  échec connexion:", type(e).__name__, str(e))
        return False


async def main():
    print("Scan BLE 10 secondes...")
    devices = await BleakScanner.discover(timeout=10, return_adv=True)

    candidates = []

    for address, (device, adv) in devices.items():
        name = device.name or adv.local_name or ""
        rssi = adv.rssi

        if name.lower() in IGNORE_NAMES:
            continue

        # On teste seulement les appareils pas trop faibles.
        if rssi < -85:
            continue

        candidates.append((rssi, address, name or "UNKNOWN"))

    candidates.sort(reverse=True)

    print("\nCandidats:")
    for rssi, address, name in candidates:
        print(f"{rssi:4} dBm | {name:30} | {address}")

    print("\nRecherche du service UART micro:bit...")

    for rssi, address, name in candidates:
        found = await try_device(address, name, rssi)

        if found:
            print("\n✅ micro:bit identifié.")
            return

    print("\n❌ Aucun micro:bit UART trouvé.")
    print("Soit le micro:bit n'annonce pas/connecte pas correctement, soit il n'est pas actif.")


asyncio.run(main())
