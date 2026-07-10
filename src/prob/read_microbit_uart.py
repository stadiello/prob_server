import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice


TARGET_NAME = "BBC micro:bit"
TARGET_ADDRESS = "F8:B4:AB:35:89:E3"

# Nordic UART Service :
# micro:bit -> Raspberry Pi : indications BLE
UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

# Raspberry Pi -> micro:bit : écriture de l'ACK
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

OUTPUT_DIR = Path("/home/pi/microbit_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Durée maximale d'attente après la connexion.
# Le micro:bit annonce pendant 20 secondes : on garde une petite marge.

SCAN_TIMEOUT_SECONDS = 45
READ_TIMEOUT_SECONDS = 25

PAUSE_AFTER_SUCCESS_SECONDS = 270
PAUSE_AFTER_NO_DATA_SECONDS = 10
PAUSE_AFTER_ERROR_SECONDS = 10


CSV_COLUMNS = [
    "raspberry_timestamp",
    "device_id",
    "seq",
    "microbit_uptime_ms",
    "temperature_c",
    "light_level",
    "sound_average_db",
    "sound_peak_db",
    "moved",
    "pitch",
    "roll",
    "acceleration",
]


def log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"{timestamp} | {message}", flush=True)


def output_path() -> Path:
    date_string = datetime.now().strftime("%Y-%m-%d")
    return OUTPUT_DIR / f"microbit_{date_string}.csv"


def ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()


def safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_payload(line: str) -> Optional[dict]:
    """
    Nouveau format attendu :

    device_id,
    seq,
    uptime_ms,
    temperature_c,
    light_level,
    sound_average_db,
    sound_peak_db,
    moved,
    pitch,
    roll,
    acceleration
    """

    parts = [part.strip() for part in line.split(",")]

    if len(parts) == 11:
        (
            device_id,
            seq,
            uptime_ms,
            temperature_c,
            light_level,
            sound_average_db,
            sound_peak_db,
            moved,
            pitch,
            roll,
            acceleration,
        ) = parts

    elif len(parts) == 6:
        # Compatibilité temporaire avec l'ancien firmware.
        (
            device_id,
            seq,
            uptime_ms,
            temperature_c,
            light_level,
            old_sound_level,
        ) = parts

        sound_average_db = old_sound_level
        sound_peak_db = old_sound_level
        moved = "0"
        pitch = "0"
        roll = "0"
        acceleration = "0"

    else:
        log(
            "Format invalide : "
            f"{len(parts)} champs reçus au lieu de 11 : {line}"
        )
        return None

    if not device_id:
        log(f"Identifiant vide : {line}")
        return None

    numeric_values = {
        "seq": seq,
        "microbit_uptime_ms": uptime_ms,
        "temperature_c": temperature_c,
        "light_level": light_level,
        "sound_average_db": sound_average_db,
        "sound_peak_db": sound_peak_db,
        "moved": moved,
        "pitch": pitch,
        "roll": roll,
        "acceleration": acceleration,
    }

    parsed_numeric_values = {}

    for field_name, value in numeric_values.items():
        parsed_value = safe_int(value)

        if parsed_value is None:
            log(
                f"Valeur invalide pour {field_name}: "
                f"{value!r} dans {line}"
            )
            return None

        parsed_numeric_values[field_name] = parsed_value

    if parsed_numeric_values["seq"] < 0:
        log(f"Séquence invalide : {line}")
        return None

    if parsed_numeric_values["moved"] not in (0, 1):
        log(f"Valeur moved invalide : {line}")
        return None

    return {
        "raspberry_timestamp": datetime.now().isoformat(timespec="seconds"),
        "device_id": device_id,
        **parsed_numeric_values,
    }


def measurement_already_saved(path: Path, device_id: str, seq: int) -> bool:
    """
    Évite d'écrire plusieurs fois une mesure répétée pendant la fenêtre BLE.

    Cette vérification lit uniquement le fichier quotidien, ce qui reste
    raisonnable pour une mesure toutes les cinq minutes.
    """

    if not path.exists():
        return False

    try:
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                if (
                    row.get("device_id") == device_id
                    and row.get("seq") == str(seq)
                ):
                    return True

    except (OSError, csv.Error) as error:
        log(f"Impossible de vérifier les doublons : {error}")

    return False


def save_measurement(measurement: dict) -> bool:
    path = output_path()
    ensure_header(path)

    device_id = measurement["device_id"]
    seq = measurement["seq"]

    if measurement_already_saved(path, device_id, seq):
        log(f"Mesure déjà enregistrée : {device_id} seq={seq}")
        return True

    try:
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writerow(measurement)

            # On force les données Python vers le système avant l'ACK.
            file.flush()

        log(f"Mesure enregistrée dans {path}")
        return True

    except OSError as error:
        log(f"Échec écriture CSV : {error}")
        return False


async def find_microbit():
    log("Recherche du micro:bit...")

    device = await BleakScanner.find_device_by_address(
        TARGET_ADDRESS,
        timeout=SCAN_TIMEOUT_SECONDS,
    )

    if device is None:
        raise RuntimeError("Micro:bit introuvable")
    log(f"Trouvé : {device.name} {device.address}")
    await asyncio.sleep(1.5)

    return device
    
async def connect_with_retry(
    device: BLEDevice,
    attempts: int = 3,
    delay_seconds: float = 2.0,
) -> BleakClient:
    """
    Tente plusieurs connexions rapides sur le même périphérique déjà trouvé,
    sans relancer un scan BLE complet.
    """

    last_error: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        client = BleakClient(device, timeout=30.0)

        try:
            log(f"Connexion BLE : tentative {attempt}/{attempts}")

            await client.connect()

            if client.is_connected:
                log("Connexion BLE établie")
                return client

            last_error = RuntimeError(
                "La connexion s'est terminée sans erreur, "
                "mais client.is_connected vaut False"
            )

        except Exception as error:
            last_error = error

            log(
                f"Échec connexion {attempt}/{attempts} : "
                f"{type(error).__name__}: {error}"
            )

        try:
            await client.disconnect()
        except Exception as disconnect_error:
            log(
                "Nettoyage de la connexion impossible : "
                f"{type(disconnect_error).__name__}: "
                f"{disconnect_error}"
            )

        if attempt < attempts:
            log(
                f"Nouvelle tentative dans {delay_seconds:g} secondes..."
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(
        f"Connexion impossible après {attempts} tentatives"
    ) from last_error

async def send_ack(
    client: BleakClient,
    device_id: str,
    seq: int,
) -> None:
    ack = f"ACK,{device_id},{seq}\n"
    encoded_ack = ack.encode("utf-8")

    await client.write_gatt_char(
        UART_RX_UUID,
        encoded_ack,
        response=False,
    )

    log(f"ACK envoyé : {ack.strip()}")


async def collect_once() -> bool:
    device = await find_microbit()

    # Queue permettant au callback BLE synchrone de transmettre les lignes
    # complètes à la coroutine principale.
    line_queue: asyncio.Queue[str] = asyncio.Queue()

    receive_buffer = ""
    client: Optional[BleakClient] = None
    notifications_started = False

    def on_data(sender, data: bytearray) -> None:
        nonlocal receive_buffer

        text = bytes(data).decode("utf-8", errors="ignore")
        receive_buffer += text

        while "\n" in receive_buffer:
            line, receive_buffer = receive_buffer.split("\n", 1)
            line = line.strip()

            if line:
                line_queue.put_nowait(line)

    try:
        client = await connect_with_retry(
            device=device,
            attempts=3,
            delay_seconds=2.0,
        )

        log(f"Connecté : {client.is_connected}")

        for service in client.services:
            log(f"Service BLE : {service.uuid}")

            for characteristic in service.characteristics:
                log(
                    f"  Caractéristique : {characteristic.uuid} "
                    f"propriétés={characteristic.properties}"
                )

        await client.start_notify(UART_TX_UUID, on_data)
        notifications_started = True

        log(
            "En attente d'une mesure valide pendant "
            f"{READ_TIMEOUT_SECONDS} secondes..."
        )

        deadline = (
            asyncio.get_running_loop().time()
            + READ_TIMEOUT_SECONDS
        )

        processed_keys = set()

        while True:
            remaining_time = (
                deadline
                - asyncio.get_running_loop().time()
            )

            if remaining_time <= 0:
                raise asyncio.TimeoutError

            line = await asyncio.wait_for(
                line_queue.get(),
                timeout=remaining_time,
            )

            log(f"Reçu : {line}")

            measurement = parse_payload(line)

            if measurement is None:
                continue

            key = (
                measurement["device_id"],
                measurement["seq"],
            )

            # Le firmware renvoie le même payload toutes les deux secondes.
            if key in processed_keys:
                log(
                    "Répétition ignorée : "
                    f"{key[0]} seq={key[1]}"
                )
                continue

            processed_keys.add(key)

            saved = save_measurement(measurement)

            if not saved:
                # Aucun ACK : le micro:bit continuera à retransmettre.
                log(
                    "Mesure non acquittée car l'écriture CSV "
                    "a échoué"
                )
                continue

            await send_ack(
                client,
                measurement["device_id"],
                measurement["seq"],
            )

            # Laisse le temps au contrôleur Bluetooth de transmettre l'ACK.
            await asyncio.sleep(0.25)

            return True

    except asyncio.TimeoutError:
        log("Aucune mesure valide reçue avant expiration.")
        return False

    finally:
        if client is not None:
            if notifications_started and client.is_connected:
                try:
                    await client.stop_notify(UART_TX_UUID)
                except Exception as error:
                    log(
                        "Arrêt des notifications impossible : "
                        f"{type(error).__name__}: {error}"
                    )

            if client.is_connected:
                try:
                    await client.disconnect()
                    log("Déconnexion BLE effectuée")
                except Exception as error:
                    log(
                        "Déconnexion impossible : "
                        f"{type(error).__name__}: {error}"
                    )

async def main() -> None:
    log("Démarrage du logger BLE micro:bit")

    while True:
        try:
            success = await collect_once()

            if success:
                log("Cycle terminé avec ACK")
                log(
                    f"Pause {PAUSE_AFTER_SUCCESS_SECONDS} secondes "
                    "avant d'attendre la prochaine mesure"
                )
                await asyncio.sleep(PAUSE_AFTER_SUCCESS_SECONDS)

            else:
                log("Cycle terminé sans ACK")
                log(
                    f"Nouvelle tentative dans "
                    f"{PAUSE_AFTER_NO_DATA_SECONDS} secondes"
                )
                await asyncio.sleep(PAUSE_AFTER_NO_DATA_SECONDS)

        except asyncio.CancelledError:
            log("Arrêt demandé")
            raise

        except Exception as error:
            log(f"Erreur : {type(error).__name__}: {error}")
            log(
                f"Pause {PAUSE_AFTER_ERROR_SECONDS} secondes "
                "après erreur"
            )
            await asyncio.sleep(PAUSE_AFTER_ERROR_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Logger arrêté")
