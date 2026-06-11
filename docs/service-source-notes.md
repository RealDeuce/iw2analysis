# ImageWriter II Service Documentation Notes

This file captures hardware/service facts from the newly added `Sams_Technical_Imagewriter_II.pdf` and `Service_Source_Imagewriter_II.pdf`. The two documents cover related but not identical hardware revisions, so IC numbers are kept separate.

## Apple Service Source: ImageWriter II/L

Source file: `Service_Source_Imagewriter_II.pdf`.

Board structure:

- Power supply board
- Main board
- Sub PCB board
- Print head board
- Operation panel board

Main board roles:

- `IC10` ROM contains startup routines, character sets, and self-test routines.
- `IC9` RAM is used as the print data buffer and is cleared by power-off.
- `IC8` CPU and `IC4` gate array jointly control data transfer, printing decisions, motor control, and printed output.
- `IC2` and `IC3` interface circuits handle host data, status, and control lines through the sub PCB.
- `IC5` and `IC6` print-head drivers process print-head drive signals from the CPU and gate array.

Clocks:

- Gate array `IC4` uses crystal `X1` at 17.2 MHz.
- CPU `IC8` uses crystal `X2` at 12 MHz.

Self-test:

- Start by holding Form Feed while turning power on.
- With a color ribbon, output alternates colors by line.
- First output includes ROM revision, DIP switch settings, and option-card status.
- Then it prints lines containing alphabetic, numeric, and special characters.

I/O:

- Standard asynchronous serial interface.
- LocalTalk is available with an option board.
- Protocol is switch selectable: hardware data-ready/busy handshake or XON/XOFF.
- Data format is asynchronous serial with no parity bit.
- Speeds are 300, 1200, 2400, and 9600 baud.

## Sams Computerfacts: ImageWriter II

Source file: `Sams_Technical_Imagewriter_II.pdf`.

Logic-board part identifiers:

| IC | Sams/Apple marking | Current interpretation |
| --- | --- | --- |
| `IC1` | `AM26LS30PC` | Serial line driver. |
| `IC2` | `M74LS158P` | Data selector/multiplexer used in loopback/interface path. |
| `IC3` | `AM26LS32ACN` | Serial line receiver. |
| `IC4` | `M74LS123P` | One-shot/timing logic. |
| `IC5` | `EC-A042` | Clock/RAM control. |
| `IC6` | `EC-A041` / `2106AF001` | Head/carrier motor control. |
| `IC7` | `TA75393P` | Driver/comparator support device. |
| `IC8` | `M53206P` | Inverter/driver support device. |
| `IC9` | `EC-A056` | CPU. |
| `IC10` | `04168C-15` | ROM. |
| `IC11` | `EC-A137` / `7247-A137` | Apple/custom support device. |
| `IC12` | `M74LS373P` | Latch. |

Probe points and clocks:

- CPU `IC9` pin 31: 12.0 MHz oscillator.
- CPU `IC9` pin 28: reset, low for about 60 ms at power-on, then high.
- Clock/RAM control `IC5` pin 21: 17.2 MHz oscillator.
- Clock/RAM control `IC5` pin 7: 8.6 MHz clock.
- CPU `IC9` pin 20: 614 kHz clock.
- CPU `IC9` pin 19: serial clock, 16x selected baud:
  - 300 baud: 4800 Hz
  - 1200 baud: 19.2 kHz
  - 2400 baud: 38.4 kHz
  - 9600 baud: 153.6 kHz

Built-in tests:

- Self-test starts by holding Form Feed during power-on.
- Line Feed held during power-on moves the carriage back and forth without printing or line feeds.
- Loopback test starts by holding Print Quality during power-on.
- Loopback adapter wiring: handshake pins 1 and 2 together, data pins 3 and 5 together.
- Loopback failure prints `LOOP BACK TESTS FAILS` according to Sams OCR; the ROM string at `0x272D` reads `LOOP BACK TEST FAILS`.

DIP switch summary matches the programmer reference:

- `SW1-1` through `SW1-3`: national character set.
- `SW1-4`: 11-inch vs 12-inch form length.
- `SW1-5`: perforation skip.
- `SW1-6`/`SW1-7`: pica, elite, ultracondensed, or 160 dpi proportional.
- `SW1-8`: CR only vs CR plus LF.
- `SW2-1`/`SW2-2`: baud rate.
- `SW2-3`: hardware handshake vs XON/XOFF.
- `SW2-4`: option card disabled/enabled.
- `SW2-5`/`SW2-6`: factory hammer-fire timing; do not adjust except for alignment/service procedure.

