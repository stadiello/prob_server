import asyncio
import csv
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner

TARGET_NAME = "BBC micro:bit"
TARGET_ADDRESS = "F8:B4:AB:35:89:E3"

# UUIDs réellement exposés par ton micro:bit
UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # micro:bit -> Raspberry Pi
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Raspberry Pi -> micro:bit

OUTPUT_DIR = Path("/home/pi/microbit_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCAN_TIMEOUT_SECONDS = 20
READ_DURATION_SECONDS = 20
PAUSE_BETWEEN_CYCLES_SECONDS = 30
PAUSE_AFTER_ERROR_SECONDS = 10

buffer = ""


def log(message: str) -> None:
    print(f"{datetime.now().isoformat(timespec='seconds')} | {message}", flush=True)


def output_path() -> Path:
    return OUTPUT_DIR / f"microbit_{datetime.now().strftime('%Y-%m-%d')}.csv"


def ensure_header(path: Path) -> None:
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


async def find_microbit():
    return await BleakScanner.find_device_by_filter(
        lambda d, ad: (
            d.address == TARGET_ADDRESS
            or (d.name is not None and TARGET_NAME in d.name)
            or (ad.local_name is not None and TARGET_NAME in ad.local_name)
        ),
        timeout=SCAN_TIMEOUT_SECONDS,
    )


async def collect_once() -> bool:
    global buffer
    buffer = ""

    log("Recherche du micro:bit...")
    device = await find_microbit()

    if device is None:
        log("micro:bit non trouvé")
        return False

    log(f"Trouvé: {device.name} {device.address}")
    log("Connexion...")

    received_lines = []

    def on_data(sender, data):
        global buffer

        text = data.decode("utf-8", errors="ignore")
        buffer += text

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()

            if line:
                received_at = datetime.now().isoformat(timespec="seconds")
                log(f"Reçu: {line}")
                received_lines.append((received_at, line))

    async with BleakClient(device, timeout=30.0) as client:
        log(f"Connecté: {client.is_connected}")

        await client.start_notify(UART_TX_UUID, on_data)

        log(f"Lecture pendant {READ_DURATION_SECONDS} secondes...")
        await asyncio.sleep(READ_DURATION_SECONDS)

        await client.stop_notify(UART_TX_UUID)

    if not received_lines:
        log("Connexion OK, mais aucune donnée reçue.")
        return True

    path = output_path()
    ensure_header(path)

    with path.open("a", newline="") as f:
        writer = csv.writer(f)

        for received_at, line in received_lines:
            parts = line.split(",")

            if len(parts) != 6:
                log(f"Ignoré, format invalide: {line}")
                continue

            device_id, seq, uptime_ms, temp_c, light, sound = parts

            writer.writerow([
                received_at,
                device_id,
                seq,
                uptime_ms,
                temp_c,
                light,
                sound,
            ])

    log(f"CSV écrit dans: {path}")
    return True


async def main():
    log("Démarrage du logger BLE micro:bit")

    while True:
        try:
            await collect_once()
            log(f"Pause {PAUSE_BETWEEN_CYCLES_SECONDS} secondes avant prochain cycle")
            await asyncio.sleep(PAUSE_BETWEEN_CYCLES_SECONDS)

        except Exception as e:
            log(f"Erreur: {type(e).__name__}: {e}")
            log(f"Pause {PAUSE_AFTER_ERROR_SECONDS} secondes après erreur")
            await asyncio.sleep(PAUSE_AFTER_ERROR_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
