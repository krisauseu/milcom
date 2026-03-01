# MilCom - Military Aircraft Monitor

MilCom is a lightweight, web-based dashboard designed to monitor military aircraft traffic in real-time. It fetches ADS-B data from a local receiver and applies specialized filters to highlight military assets, providing a clear overview of tactical air movements.

![MilCom Dashboard](milcom.png)

## How It Works

The application acts as a middleman between your ADS-B receiver and a web interface. It continuously polls the JSON data provided by **SkyAware/Piaware** and filters for specific aircraft based on:

*   **ICAO Hex Ranges**: Targets known military blocks globally (US DoD, UK MoD, Luftwaffe, NATO, etc.).
*   **Callsign Patterns**: Monitors for tactical callsigns like `FORTE` (Global Hawk), `LAGR` (Tankers), `NATO` (AWACS), and many more.
*   **Role Identification**: Automatically categorizes aircraft into roles such as *Tanker*, *ISR*, *Transport*, *Fighter*, or *Special Ops*.

## Hardware Requirements

To use this dashboard, you need a local ADS-B receiving setup:

*   **Raspberry Pi** (or similar SBC/Server).
*   **ADS-B Receiver** (e.g., FlightAware Pro Stick or RTL-SDR).
*   **Antenna** tuned for 1090 MHz.
*   **Software**: Piaware or a standard dump1090-fa installation with SkyAware enabled.

## Features

*   **Real-time Map**: Visualizes aircraft positions with history trails.
*   **Military Focus**: Specifically tuned to filter out civilian traffic and show only relevant military/government flights.
*   **Type Recognition**: Identifies specific airframes (e.g., C-17 Globemaster, KC-135 Stratotanker, Eurofighter) using a built-in database.
*   **Filter Logic**: Heuristic-based detection of tankers, AWACS, and reconnaissance aircraft even when type data is missing.
*   **Auth Protected**: Simple basic authentication for secure remote access.

## Installation via Docker Compose

The easiest way to run MilCom is using Docker Compose.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/krisauseu/milcom.git
    cd milcom
    ```

2.  **Configure the receiver IP**:
    Edit the `docker-compose.yml` file and set the `PI_IP` environment variable to the IP address of your Raspberry Pi running Piaware.

    ```yaml
    environment:
      - PI_IP=192.168.1.100  # Change to your Pi's IP
      - AUTH_USER=admin
      - AUTH_PASS=yourpassword
    ```

3.  **Start the container**:
    ```bash
    docker-compose up -d
    ```

4.  **Access the Dashboard**:
    Open your browser and navigate to `http://<your-server-ip>:5050`.

## License

This project is for educational and hobbyist use. Data accuracy depends on your local receiver coverage and the heuristics used for identification.
