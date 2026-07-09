import asyncio
import csv
from datetime import datetime
from pathlib import Path

from bleak import BleakScanner, BleakClient

DEVICE_NAME_PART = "micro:bit"

UART_SERVICE_UUID = "e95d5400-251d-470a-a062-fa1922dfa9a8"
UART_TX_UUID = "e95d540b-251d-470a-a062-fa1922dfa9a8"  # micro:bit -> Pi
UART_RX_UUID = "e95d540a-251d-470a-a062-fa1922dfa9a8"  # Pi -> micro:bit

OUTPUT_DIR = Path("/home/pi/microbit_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

buffer = ""


def output_path():
    return OUTPUT_DIR / f"microbit_{datetime.now().strftime('%Y-%m-%d')}.csv"


def ensure_header(path):
    if not path.exists():
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "raspberry_timestamp",
                "device_id",
                "seq",
                "microbit_uptime_ms",
                "temperature_c",
                "light_level",
                "sound_level",
            ])


async def collect_once():
    global buffer
    buffer = ""

    print("Scan BLE...")

    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name is not None and DEVICE_NAME_PART.lower() in d.name.lower(),
        timeout=10.0,
    )

    if device is None:
        print("Aucun micro:bit trouvé.")
        return False

    print(f"Connexion à {device.name}...")

    received_line = None

    def handle_rx(sender, data):
        nonlocal received_line
        global buffer

        text = data.decode("utf-8", errors="ignore")
        buffer += text

        if "\n" in buffer:
            line, _, rest = buffer.partition("\n")
            buffer = rest
            received_line = line.strip()

    async with BleakClient(device) as client:
        await client.start_notify(UART_TX_UUID, handle_rx)

        # On attend une ligne venant du micro:bit
        deadline = asyncio.get_event_loop().time() + 8.0

        while received_line is None and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.1)

        if received_line is None:
            print("Connexion OK mais aucune donnée reçue.")
            return False

        print("Reçu:", received_line)

        parts = received_line.split(",")

        if len(parts) != 6:
            print("Format invalide:", received_line)
            return False

        device_id, seq, uptime_ms, temp_c, light, sound = parts

        path = output_path()
        ensure_header(path)

        with path.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                device_id,
                seq,
                uptime_ms,
                temp_c,
                light,
                sound,
            ])

        ack = f"ACK,{seq}\n".encode("utf-8")
        await client.write_gatt_char(UART_RX_UUID, ack, response=False)

        print("ACK envoyé:", ack.decode().strip())

        await client.stop_notify(UART_TX_UUID)

    return True


async def main():
    while True:
        try:
            await collect_once()
        except Exception as e:
            print("Erreur:", repr(e))

        # Le Pi tente régulièrement. Le micro:bit, lui, reste économe.
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
