# MilCom - Military Aircraft Monitor

MilCom is a lightweight, web-based dashboard designed to monitor military aircraft traffic in real-time. It fetches ADS-B data from a local receiver and applies specialized filters to highlight military assets, providing a clear overview of tactical air movements.

![MilCom Dashboard](milcom.png)

## Filtering & Identification

MilCom uses a strict, multi-layered filtering system to ensure a pure military tactical display:

### 1. Strict Callsign Filter
Only aircraft with specific military callsign prefixes are allowed through. This includes:
*   **US/NATO Transport & AWACS**: `RCH`, `C5`, `C17`, `C130`, `CNV`, `NATO`, `MAGIC`
*   **European Air Forces**: `GAF`, `GNY` (Germany), `RRR`, `ASCOT` (UK), `BAF` (Belgium), `NAF` (Netherlands), `FAF`, `AME` (France), `POL` (Poland), etc.
*   **Special Ops & ISR**: `DUKE`, `VADER`, `JAKE`, `FORTE`
*   **Tankers**: `LAGR`, `NCHO`, `QID`, `GOLD`, `TEX`, `TARTN`

### 2. Precise HEX Ranges
Beyond callsigns, MilCom tracks thousands of specific ICAO hex addresses belonging to military airframes. National blocks are narrowed down to military-only sub-ranges (e.g., US Military `AE0000-AFFFFF`) to exclude civilian aircraft from the same country.

### 3. Emergency Exceptions
Any aircraft broadcasting an **Emergency Squawk** (`7700` General Emergency, `7600` Radio Failure, `7500` Hijack) is **ALWAYS** displayed, regardless of its origin or type.

### 4. Country Fallback Identification
If a specific aircraft type is not in our database, MilCom uses its HEX range to identify the country of origin. Instead of a blank entry, you will see labels like `TUR`, `GRC`, or `DEU`.

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
