# Smart Climate Controller

A MicroPython-based climate-monitoring and control project for the Yolo Uno board. It reads temperature and humidity from a DHT20 sensor, displays readings on an LCD1602, and runs independent asynchronous tasks to represent cooling, temperature status, and humidification behavior.

## Features

- Reads temperature and humidity from a DHT20 sensor at five-second intervals.
- Displays readings or sensor-error messages on an LCD1602.
- Uses separate asynchronous tasks for sensor reading, cooler behavior, temperature status, humidifier behavior, and a blinking indicator LED.
- Passes structured `SensorMessage` objects between tasks through separate bounded message queues.
- Implements a lightweight custom `Semaphore` and `MessageQueue`.
- Provides optional automatic test cases for normal readings, low/high temperature, low humidity, hot-and-dry conditions, and simulated sensor failure.
- Uses RGB LEDs to indicate temperature states and simulated cooler/humidifier activity.

## Hardware and Libraries

The source imports these board-specific modules:

- `yolo_uno`
- `pins`
- `lcd1602`
- `dht20`

The hardware abstraction in the code uses a DHT20 sensor, LCD1602 display, one indicator LED, and RGB LEDs connected through the project's `Pins` and `RGBLed` wrappers. Confirm the actual board wiring and library setup for your device or simulator.

## Behavior

### Temperature status

The temperature-status task uses these thresholds:

| Temperature | Status | RGB indication |
|---|---|---|
| Below 16°C | Critical low | Red |
| 16°C to below 20°C | Warning low | Orange |
| 20°C to 28°C | Safe | Green |
| Above 28°C to 32°C | Warning high | Orange |
| Above 32°C | Critical high | Red |

The cooler indication runs for five seconds when a valid reading is above 28°C. The humidifier indication sequence runs when humidity is below 40%: green for five seconds, yellow for three seconds, then red for two seconds. These are indicator/behavior simulations in the provided code; the code does not show physical heater, cooler, or humidifier driver circuits.

## Task and Message Design

1. The sensor task obtains a reading or records a sensor error.
2. It packages the result in a `SensorMessage` containing temperature, humidity, error state, data availability, and a sequence number.
3. It publishes the message to separate queues for the cooler, temperature-status, and humidifier tasks.
4. Each task consumes its own queue so it can process readings independently.

Each queue has capacity one. When full, the queue discards its older pending item and keeps the newest one. This favors fresh sensor readings over processing a backlog.

## Running and Testing

1. Open the project in the environment that provides the Yolo Uno MicroPython libraries.
2. Confirm that the board/simulator supports `create_task`, `asleep_ms`, and `run_loop`.
3. Set `TEST_MODE = False` to read from the DHT20 sensor.
4. Set `TEST_MODE = True` to cycle through the built-in test cases.
5. Start the program and observe the LCD and serial output.

The automatic test provider holds each case for three readings. At a five-second sampling interval, each case lasts about 15 seconds.

## Limitations and Notes

- The code depends on Yolo Uno-specific modules and is not directly portable to standard desktop Python without compatible hardware libraries or stubs.
- The cooler, heater, and humidifier are represented by RGB LED behavior; physical actuator control is not implemented in the provided source.
- The custom semaphore and queue are educational implementations. They should be validated carefully if adapted to a different scheduler or runtime.
- A sensor error turns off the cooler/humidifier indicators and marks the temperature status as a sensor error.
- The code shown does not include a wiring diagram or a full bill of materials.

## Technologies

MicroPython, asynchronous tasks, semaphores, bounded message queues, DHT20, LCD1602, RGB LEDs, Yolo Uno.
