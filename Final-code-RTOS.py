from yolo_uno import *
from pins import *
from lcd1602 import *
from dht20 import *


# ============================================================
# SEMAPHORE AND QUEUE
# ============================================================

class Semaphore:
    def __init__(self, value=1):
        if value < 0:
            raise ValueError(
                "Semaphore value must not be negative"
            )

        self.value = value

    async def acquire(self):
        # Use 100 ms to reduce simulator workload.
        while self.value <= 0:
            await asleep_ms(100)

        self.value -= 1
        return True

    def release(self):
        self.value += 1


class MessageQueue:

    def __init__(self, capacity=1):
        if capacity <= 0:
            raise ValueError(
                "Queue capacity must be greater than zero"
            )

        self.capacity = capacity
        self.items = []
        self.item_ready = Semaphore(0)

    def put(self, item):
        if len(self.items) >= self.capacity:
            # The number of queued items does not change, so the
            # semaphore count must not be increased.
            self.items.pop(0)
        else:
            self.item_ready.release()

        self.items.append(item)

    async def get(self):
        await self.item_ready.acquire()
        return self.items.pop(0)


# ============================================================
# STRUCTURED SENSOR MESSAGE
# ============================================================

class SensorMessage:
    def __init__(
        self,
        temperature,
        humidity,
        sensor_error,
        data_available,
        sequence,
    ):
        self.temperature = temperature
        self.humidity = humidity
        self.sensor_error = sensor_error
        self.data_available = data_available
        self.sequence = sequence


# ============================================================
# HARDWARE CONTAINER
# ============================================================

class Hardware:
    def __init__(self):
        self.led_D13 = Pins(D13_PIN)

        self.rgb_led_D3 = RGBLed(D3_PIN, 4)
        self.rgb_led_D5 = RGBLed(D5_PIN, 4)
        self.rgb_led_D7 = RGBLed(D7_PIN, 4)

        self.lcd1602 = LCD1602()
        self.dht20 = DHT20()


# ============================================================
# TASK QUEUE CONTAINER
# ============================================================

class TaskQueues:
    def __init__(self):
        # Each actuator receives every sensor message through its own
        # bounded queue. One pending message is retained per task.
        self.heater = MessageQueue(1)
        self.cooler = MessageQueue(1)
        self.humidifier = MessageQueue(1)


# ============================================================
# COLORS
# ============================================================

COLOR_OFF = hex_to_rgb("#000000")
COLOR_GREEN = hex_to_rgb("#00ff00")
COLOR_ORANGE = hex_to_rgb("#ff3000")
COLOR_YELLOW = hex_to_rgb("#ffff00")
COLOR_RED = hex_to_rgb("#ff0000")


# ============================================================
# CONFIGURATION
# ============================================================

# These are read-only configuration constants, not mutable shared
# variables used for communication between tasks.

# False: read values from the simulated DHT20 sliders
# True: use the automatic test cases defined below
TEST_MODE = False

BLINK_PERIOD_MS = 1000
SENSOR_PERIOD_MS = 5000
COOLER_RUN_TIME_MS = 5000

HUMIDIFIER_GREEN_TIME_MS = 5000
HUMIDIFIER_YELLOW_TIME_MS = 3000
HUMIDIFIER_RED_TIME_MS = 2000

CRITICAL_TEMP_MIN = 16
SAFE_TEMP_MIN = 20
SAFE_TEMP_MAX = 28
CRITICAL_TEMP_MAX = 32

COOLER_THRESHOLD = 28
HUMIDITY_THRESHOLD = 40


# ============================================================
# AUTOMATIC TEST DATA
# ============================================================

# Each test case is used for three sensor readings.
# Three readings x five seconds = 15 seconds per test case.
TEST_CASE_HOLD_READS = 3

TEST_CASES = (
    (
        "SAFE TEMP / NORMAL HUMIDITY",
        25,
        55,
        False,
    ),
    (
        "WARNING LOW TEMPERATURE",
        18,
        55,
        False,
    ),
    (
        "CRITICAL LOW TEMPERATURE",
        14,
        55,
        False,
    ),
    (
        "WARNING HIGH + COOLER",
        30,
        55,
        False,
    ),
    (
        "CRITICAL HIGH + COOLER",
        35,
        55,
        False,
    ),
    (
        "LOW HUMIDITY",
        25,
        35,
        False,
    ),
    (
        "HOT AND DRY",
        31,
        30,
        False,
    ),
    (
        "SIMULATED SENSOR ERROR",
        0,
        0,
        True,
    ),
)


class TestDataProvider:
    def __init__(self, test_cases, hold_reads):
        self.test_cases = test_cases
        self.hold_reads = hold_reads
        self.case_index = 0
        self.read_count = 0

    def get_next(self):
        test_case = self.test_cases[self.case_index]
        self.read_count += 1

        if self.read_count >= self.hold_reads:
            self.read_count = 0
            self.case_index = (
                self.case_index + 1
            ) % len(self.test_cases)

        return test_case


# ============================================================
# GENERAL HELPERS
# ============================================================

def show_all(rgb_led, color):
    for index in range(4):
        rgb_led.show(index, color)


def turn_all_actuators_off(hardware):
    show_all(hardware.rgb_led_D3, COLOR_OFF)
    show_all(hardware.rgb_led_D5, COLOR_OFF)
    show_all(hardware.rgb_led_D7, COLOR_OFF)


def format_sensor_value(value):
    try:
        return "{:.1f}".format(float(value))
    except Exception:
        return str(value)


def publish_sensor_message(task_queues, message):
    # The same read-only message is delivered to every actuator.
    task_queues.heater.put(message)
    task_queues.cooler.put(message)
    task_queues.humidifier.put(message)


# ============================================================
# TASK 1: BLINKY
# ============================================================

async def task_LED_Blinky(hardware):
    while True:
        hardware.led_D13.toggle()
        await asleep_ms(BLINK_PERIOD_MS)


# ============================================================
# TASK 2: READ TEMPERATURE AND HUMIDITY
# ============================================================

async def task_Read_Temperature(
    hardware,
    task_queues,
    test_data_provider,
):
    # Sequence is local to this task rather than a global variable.
    sequence = 0

    while True:
        sequence += 1

        try:
            if TEST_MODE:
                (
                    label,
                    temperature,
                    humidity,
                    simulate_error,
                ) = test_data_provider.get_next()

                print("")
                print(
                    "========================================"
                )
                print("[TEST CASE]", label)
                print(
                    "========================================"
                )

                if simulate_error:
                    raise RuntimeError(
                        "Simulated DHT20 sensor failure"
                    )

            else:
                temperature = (
                    await hardware.dht20.atemperature()
                )
                humidity = (
                    await hardware.dht20.ahumidity()
                )

            message = SensorMessage(
                temperature,
                humidity,
                False,
                True,
                sequence,
            )

            print("==============================")
            print(
                "[SENSOR] Temperature:",
                temperature,
                "C",
            )
            print(
                "[SENSOR] Humidity:",
                humidity,
                "%",
            )
            print("==============================")

            hardware.lcd1602.clear()
            hardware.lcd1602.show(
                (
                    "Temp:"
                    + format_sensor_value(temperature)
                    + "C"
                ),
                0,
                0,
            )
            hardware.lcd1602.show(
                (
                    "Humi:"
                    + format_sensor_value(humidity)
                    + "%"
                ),
                1,
                0,
            )

        except Exception as error:
            message = SensorMessage(
                0,
                0,
                True,
                False,
                sequence,
            )

            print(
                "[ERROR] Cannot read DHT20:",
                error,
            )

            hardware.lcd1602.clear()
            hardware.lcd1602.show(
                "Sensor error",
                0,
                0,
            )
            hardware.lcd1602.show(
                "Check DHT20",
                1,
                0,
            )

        # The complete data object is transferred through queues.
        publish_sensor_message(task_queues, message)

        await asleep_ms(SENSOR_PERIOD_MS)


# ============================================================
# TASK 3: COOLER
# ============================================================

async def task_Cooler(hardware, cooler_queue):
    while True:
        message = await cooler_queue.get()

        if (
            message.sensor_error
            or not message.data_available
        ):
            show_all(hardware.rgb_led_D5, COLOR_OFF)

            print(
                "[COOLER] Sensor unavailable "
                "-> Cooler OFF"
            )
            continue

        if message.temperature > COOLER_THRESHOLD:
            print(
                "[COOLER] Reading #",
                message.sequence,
                "- Temperature:",
                message.temperature,
                "C -> Cooler ON",
            )

            show_all(
                hardware.rgb_led_D5,
                COLOR_GREEN,
            )

            await asleep_ms(COOLER_RUN_TIME_MS)

            show_all(hardware.rgb_led_D5, COLOR_OFF)

            print(
                "[COOLER] Five-second cycle "
                "completed -> Cooler OFF"
            )

        else:
            show_all(hardware.rgb_led_D5, COLOR_OFF)

            print(
                "[COOLER] Temperature:",
                message.temperature,
                "C -> Cooler not required",
            )


# ============================================================
# TASK 4: HEATER / TEMPERATURE STATUS
# ============================================================

async def task_Heater(hardware, heater_queue):
    last_state = None

    while True:
        message = await heater_queue.get()

        if (
            message.sensor_error
            or not message.data_available
        ):
            state = "SENSOR ERROR"
            color = COLOR_OFF

        elif message.temperature < CRITICAL_TEMP_MIN:
            state = "CRITICAL LOW"
            color = COLOR_RED

        elif message.temperature < SAFE_TEMP_MIN:
            state = "WARNING LOW"
            color = COLOR_ORANGE

        elif message.temperature <= SAFE_TEMP_MAX:
            state = "SAFE"
            color = COLOR_GREEN

        elif message.temperature <= CRITICAL_TEMP_MAX:
            state = "WARNING HIGH"
            color = COLOR_ORANGE

        else:
            state = "CRITICAL HIGH"
            color = COLOR_RED

        if state != last_state:
            show_all(hardware.rgb_led_D3, color)

            print(
                "[HEATER] Reading #",
                message.sequence,
                "- Temperature:",
                message.temperature,
                "C - State:",
                state,
            )

            last_state = state


# ============================================================
# TASK 5: HUMIDIFIER
# ============================================================

async def task_Humidifier(
    hardware,
    humidifier_queue,
):
    while True:
        message = await humidifier_queue.get()

        if (
            message.sensor_error
            or not message.data_available
        ):
            show_all(hardware.rgb_led_D7, COLOR_OFF)

            print(
                "[HUMIDIFIER] Sensor unavailable "
                "-> Humidifier OFF"
            )
            continue

        if message.humidity < HUMIDITY_THRESHOLD:
            print(
                "[HUMIDIFIER] Reading #",
                message.sequence,
                "- Humidity:",
                message.humidity,
                "% -> Sequence started",
            )

            # State 1: GREEN for five seconds
            show_all(
                hardware.rgb_led_D7,
                COLOR_GREEN,
            )
            print(
                "[HUMIDIFIER] GREEN state "
                "- 5 seconds"
            )
            await asleep_ms(
                HUMIDIFIER_GREEN_TIME_MS
            )

            # State 2: YELLOW for three seconds
            show_all(
                hardware.rgb_led_D7,
                COLOR_YELLOW,
            )
            print(
                "[HUMIDIFIER] YELLOW state "
                "- 3 seconds"
            )
            await asleep_ms(
                HUMIDIFIER_YELLOW_TIME_MS
            )

            # State 3: RED for two seconds
            show_all(
                hardware.rgb_led_D7,
                COLOR_RED,
            )
            print(
                "[HUMIDIFIER] RED state "
                "- 2 seconds"
            )
            await asleep_ms(
                HUMIDIFIER_RED_TIME_MS
            )

            show_all(hardware.rgb_led_D7, COLOR_OFF)
            print(
                "[HUMIDIFIER] Sequence completed "
                "-> Humidifier OFF"
            )

        else:
            show_all(hardware.rgb_led_D7, COLOR_OFF)

            print(
                "[HUMIDIFIER] Humidity:",
                message.humidity,
                "% -> Humidifier not required",
            )


# ============================================================
# SETUP
# ============================================================

async def setup(
    hardware,
    task_queues,
    test_data_provider,
):
    print("")
    print(
        "========================================"
    )
    print("SMART CLIMATE CONTROLLER STARTED")
    print("TEST_MODE:", TEST_MODE)
    print(
        "========================================"
    )

    turn_all_actuators_off(hardware)

    hardware.lcd1602.clear()
    hardware.lcd1602.show(
        "Smart Climate",
        0,
        0,
    )
    hardware.lcd1602.show(
        "Starting...",
        1,
        0,
    )

    await asleep_ms(1000)

    create_task(task_LED_Blinky(hardware))
    create_task(
        task_Read_Temperature(
            hardware,
            task_queues,
            test_data_provider,
        )
    )
    create_task(
        task_Cooler(
            hardware,
            task_queues.cooler,
        )
    )
    create_task(
        task_Heater(
            hardware,
            task_queues.heater,
        )
    )
    create_task(
        task_Humidifier(
            hardware,
            task_queues.humidifier,
        )
    )


# ============================================================
# MAIN
# ============================================================

async def main():
    hardware = Hardware()
    task_queues = TaskQueues()
    test_data_provider = TestDataProvider(
        TEST_CASES,
        TEST_CASE_HOLD_READS,
    )

    await setup(
        hardware,
        task_queues,
        test_data_provider,
    )

    while True:
        await asleep_ms(100)


run_loop(main())
