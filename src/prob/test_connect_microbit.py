import asyncio
from bleak import BleakClient

ADDRESS = "F8:B4:AB:35:89:E3"

async def main():
    print("Connexion à", ADDRESS)

    async with BleakClient(ADDRESS, timeout=20) as client:
        print("Connecté:", client.is_connected)

        for service in client.services:
            print("SERVICE", service.uuid)

            for char in service.characteristics:
                print("  CHAR", char.uuid, char.properties)

asyncio.run(main())
