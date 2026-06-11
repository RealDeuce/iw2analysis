# ImageWriter II Firmware Map

ROM under analysis:

- File: `ImageWriter2_new.bin`
- Size: 32768 bytes
- `cksum`: `3282235718 32768`
- SHA-256: `06f6e22c4bce0540ce3f29579086e90babdce0913028917a152ef9d6bcdb0f41`

The ROM disassembles coherently with MAME `unidasm` using architecture `upd7810`:

```sh
../mame/unidasm ImageWriter2_new.bin -arch upd7810 -basepc 0 -count 0x8000 > disasm/iw2_upd7810_full.lst
```

The generated listing is saved at `disasm/iw2_upd7810_full.lst`.

## Source Documents

Additional service documentation now consulted:

| File | Scope | Useful details |
| --- | --- | --- |
| `Apple ImageWriter II Technical Reference Manual.pdf` | Programmer command reference | Command bytes, defaults, switch semantics, graphics and character-set behavior. |
| `Service_Source_Imagewriter_II.pdf` | Apple Service Source for ImageWriter II/L | Board roles, II/L clocks, self-test behavior, LocalTalk/sub-PCB description. |
| `Sams_Technical_Imagewriter_II.pdf` | Sams Computerfacts for ImageWriter II | Older ImageWriter II logic-board IC list, probe points, clock frequencies, loopback/self-test procedure, schematic signal names. |

## Why uPD7810

The `upd7810` decode produces plausible reset/interrupt stubs, memory setup, serial I/O register access, and subroutine flow. Earlier 6502, M740, and 6800-family trials decoded the same reset area as mostly illegal or nonsensical code.

Evidence:

- `0x0000`: reset path disables interrupts and initializes memory/peripheral state.
- `0x000D`, `0x0015`, `0x001D`, `0x0029`: direct jumps to plausible ROM handlers at `0x25F2`, `0x1B30`, `0x1B0A`, and `0x2102`.
- `0x01DB`: reads `RXB`, the receive buffer register.
- `0x21DC`: writes `TXB`, the transmit buffer register.
- `0x217A`: builds the self-ID response string beginning with ASCII `IW10`.

The last bytes at `0x7FFA-0x7FFF` are `FF`, so this image should not be treated as a 6502-style ROM with reset vectors at the file end.

## Hardware Notes From Service Docs

There are model/version differences in the service literature:

- `Service_Source_Imagewriter_II.pdf` covers the ImageWriter II/L. It names five boards: power supply, main board, sub PCB, print head board, and operation panel. On the II/L main board, ROM is `IC10`, RAM is `IC9`, CPU is `IC8`, and the gate array is `IC4`. It says gate-array crystal `X1` runs at 17.2 MHz and CPU crystal `X2` runs at 12 MHz.
- `Sams_Technical_Imagewriter_II.pdf` covers the older ImageWriter II logic board. Its parts list names CPU `IC9` as Apple part `EC-A056`, ROM `IC10` as `04168C-15`, clock/RAM control `IC5` as `EC-A042`, head/carrier motor control `IC6` as `EC-A041` / `2106AF001`, and `IC11` as `EC-A137` / `7247-A137`.
- Sams troubleshooting gives concrete probe points for the older board: 12 MHz oscillator at CPU `IC9` pin 31, reset at CPU `IC9` pin 28 low for about 60 ms at power-up, 17.2 MHz oscillator at clock/RAM control `IC5` pin 21, 8.6 MHz clock at `IC5` pin 7, 614 kHz clock at CPU `IC9` pin 20, and a serial baud-derived clock at CPU `IC9` pin 19 equal to 16x the selected baud.
- Sams also names the older board's serial interface parts: `IC1` AM26LS30 line driver, `IC2` M74LS158 data selector/multiplexer, and `IC3` AM26LS32 line receiver.

The ROM image still matches the `upd7810` instruction set well, but the service manuals use Apple/custom part numbers rather than a public CPU part number. Treat `EC-A056` as the board-level CPU part identifier until a chip marking or Apple parts list maps it to a public NEC family name.

## Memory/IO Observations

These names are descriptive, not final symbols.

| Address/range | Current interpretation | Evidence |
| --- | --- | --- |
| `0x8000` | External buffer/window or port-backed RAM | Written in interrupt/state handlers, e.g. `0x1B6B`, `0x1C05`, `0x21A5`. |
| `0xA000` | RAM region | Startup probes/clears it at `0x005E`; `0x025A` stores the text buffer base through `AA A1`. |
| `0xA8xx` | Main firmware state block | Many mode/state bytes and pointers live here. |
| `0xAAxx` | Buffer pointers and parser/render state | Used for queues, font/print positions, and output staging. |
| `0xFExx` | Device/port shadow or mapped I/O latch area | Startup initializes `FE00`, `FE06`, `FE10`, `FE60+`; motor/output routines mirror bytes here. |
| `0xFF00/0xFF01` | DIP switch shadows | `0x023A` reads/inverts `FE60`/`FE04` and stores switch values here. |
| `0xFF09` | Status/control shadow | Used in serial setup and main loop. |

## Entry Points And Anchors

| Address | Current label | Notes |
| --- | --- | --- |
| `0x0000` | reset/startup | Initializes registers, memory, timers, ports. |
| `0x000D -> 0x25F2` | interrupt/vector stub | Pushes registers, jumps to handler. Exact source pending. |
| `0x0015 -> 0x1B30` | interrupt/vector stub | Port/state interrupt path. |
| `0x001D -> 0x1B0A` | interrupt/vector stub | Motor/port interrupt path. |
| `0x0029 -> 0x2102` | interrupt/vector stub | Serial receive/transmit path. |
| `0x01DB` | receive byte from `RXB` | Chooses processing path based on flags and stores handler address in `MKH/MKL`. |
| `0x036B` | main scheduler loop | Calls repeated service routines: `0810`, `22C8`, `0AE6`, `039B`, `0459/05C3`, `0600`, `08D0`, `0664`, `07D5`, `06EA`, `074D`, `0794`. |
| `0x039B` | state-machine dispatcher | Uses `A8C4` as an index and a `TABLE` dispatch. |
| `0x1B0A` | interrupt dispatch | Dispatches to `0x2083` or `0x1D78` depending on flags. |
| `0x1B30` | port/state interrupt | Updates `FE6C-FE6F`, `AA07`, and dispatches through small state tables. |
| `0x2102` | serial interrupt entry | Checks receive/transmit flags, reads `RXB`, calls `0x2137` to buffer received bytes, and calls `0x21DC` to transmit pending bytes. |
| `0x2137` | serial receive buffer append | Writes received byte into buffer/window and updates `AA00/AA04` pointers. |
| `0x217A` | self-ID staging | Constructs `IW10C...F...CR,NUL` in `AA83+`, then sends it when output is possible. |
| `0x21DC` | serial transmit one byte | Loads next byte from `AA81` pointer and writes it to `TXB`. |
| `0x2202/0x2212` | self-test string selection | Points to `SELF TEST` or `LOOP TEST` strings at `0x26DE`/`0x26D2`. |
| `0x23AE` | emits `ESC K n` | Outputs `1B 4B` followed by a digit from `AAAC`; this is not the input handler for `ESC K`. |
| `0x2748` | main command/control loop | Fetches one parser byte with `CALT ($00B6)`, special-cases `CTRL-H`, then uses the keyed control dispatch table at `0x28B0`. |
| `0x28B0-0x28D6` | control dispatch table data | Three-byte entries of `key, target-low, target-high`; sentinel `0xFF` selects default target `0x28D7`. |
| `0x28D7` | default byte renderer/control path | Stores the current byte in `AA12`; printable bytes go to rendering, while unmatched controls go through the renderer/control fallback paths. |
| `0x2CCF` | keyed dispatch helper | Saves the fetched byte in `C`, searches a key/target table at `HL`, and returns the selected target in `EA`. |
| `0x2C07` | post-ESC command dispatcher | Fetches the byte after `ESC`, bounds it to `0x21-0x7A`, uses `TABLE` at `0x2C18`, and calls the selected handler from the table at `0x2C1B`. |
| `0x2D27` | `ESC K n` input handler | Reads color digit `0`-`6` and stores ribbon/color selection in `AA7A`. |
| `0x302A` | `ESC D` software switch set | Reads two switch mask bytes and ORs selected bits into `AA6A/AA6B`. |
| `0x3065` | `ESC Z` software switch clear | Reads two switch mask bytes and clears selected bits in `AA6A/AA6B`. |
| `0x368C` | `CTRL-H` backspace/overprint handler | Fetches the byte after backspace, computes its rendered advance, stores the backed-up position in `AA3C` within the `AA5E` boundary, resets line position through `0x275D`, then renders the saved byte through `0x28D7`. |
| `0x37C8 -> 0x275D` | `CTRL-X` current-line erase | Cancels the not-yet-printed current line without invoking the CR/LF/FF print-trigger gate or paper-feed path. |
| `0x3688` | `ESC ?` table target | Jumps directly to `0x217A` self-ID staging. |
| `0x41AD` | glyph/control metric comparison | Compares a decoded glyph/control metric against `0x1B`; this is renderer-side logic, not raw ESC command parsing. |
| `0x43CF` | hardware alert/control path | Startup/status path reaches this for code `0x07` under conditions at `0x017C-0x0184`; print-parser rendering for literal `0x07` is resolved separately as non-printing. |

## Built-In Self-Test And Loopback

Strings are mixed into code/data and are often `FF`-terminated.

| Address | Text |
| --- | --- |
| `0x26D2` | `LOOP TEST` |
| `0x26DE` | `SELF TEST` |
| `0x26EA` | `ROMREV(` |
| `0x26F6` | `DIPSW1(` |
| `0x2700` | `DIPSW2(` |
| `0x2708` | `),'1=ON,0=OFF'` |
| `0x2719` | `RAM= ` |
| `0x271F` | ` KB  AT=` |
| `0x272D` | `LOOP BACK TEST FAILS` |

The Service Source and Sams manuals both say the self-test is started by holding Form Feed while turning the printer on. The printout starts with ROM revision, DIP switch settings, and option-card information, then prints a repeated character/ripple pattern. With a color ribbon, the self-test alternates colors by line.

Sams documents a built-in loopback test started by holding Print Quality while powering on, with an adapter that connects Mini-DIN handshake pins 1 and 2 together and data pins 3 and 5 together. The ROM string `LOOP BACK TEST FAILS` at `0x272D` is the failure message for that test.

## Command Mapping Status

The documentation-level command set is in `docs/imagewriter-ii-command-reference.md`.
The ROM-linked command map is in `docs/rom-command-map.md`.

Firmware linkage summary:

| Command/function | Firmware anchor | Confidence | Notes |
| --- | --- | --- | --- |
| Serial input buffering | `0x2102`, `0x2137` | high | Uses `RXB`, queue pointers, and buffer writes. |
| Serial output / host response | `0x21DC` | high | Writes `TXB`. |
| Control-character dispatch | `0x2748`, table at `0x28B0`, default `0x28D7` | high | Handles single-byte controls before printable rendering. Per-control anchors are in `docs/rom-command-map.md`. |
| ESC command dispatch | `0x2C07`, table at `0x2C1B` | high | `TABLE` loads `BC`, then `CALB` invokes the handler. Unsupported slots mostly map to `0x368B`. |
| Self-ID (`ESC ?`) response payload | `0x3688 -> 0x217A` | high | `ESC ?` is a table entry that jumps to the ASCII `IW10...CR,NUL` response builder. |
| Self-test/loop-test print strings | `0x2202-0x229F`, strings at `0x26D2+` | high | Direct string pointers and output calls. |
| `CTRL-G` rendering behavior | `0x28D7`; hardware/status path `0x017C-0x0184`, `0x43CF` | high for rendering | Literal `0x07` is non-printing. High-bit `0x87` can render as a ROM high-ASCII glyph only when the eighth bit is included. |
| Backspace/overprint (`CTRL-H`) | `0x274A -> 0x368C` | high | Lookahead overprint path. It renders the following byte at the backed-up position without erasing the previous glyph. |
| Current-line erase (`CTRL-X`) | `0x37C8 -> 0x275D` | high | Takes effect when parsed from the buffered input stream. It clears unprinted staged line contents and leaves already printed output untouched. |
| Carriage return and related controls | `0x36F5`, `0x3706`, `0x370D`, `0x3718`, `0x3799+` | high | Main table directly maps CR, double-width, tab, LF, VT, FF, and blank-line controls to these handlers. |
| Paper feed record builders | `0x3DDD`, `0x3DF5`, `0x3DFE`, `0x3E07`, `0x3B8C` | high | Parser handlers enqueue vertical-motion records with direction from `AA6C`; motor/scheduler routines consume them later. |
| Page length and top-of-form state | `0x3AAF`, `0x31F6`, `0x3263` | high | Reset and `ESC H` initialize `A8DA/A8DC/A8DE/A8E0`; `ESC v` resets only current form position `A8E0`. |
| Perforation skip software switch | `0x302A`, `0x3065` | high | `AA6B bit 0x04` set means skip disabled, clear means enabled; transitions update `A8DC/A8DE/A8E0`. |
| Feed direction (`ESC f`/`ESC r`) | `0x32F4`, `0x32FC` | high | Stores `AA6C = 0x00` for forward or `AA6C = 0x04` for reverse. |
| Paper-out sensor commands (`ESC O`/`ESC o`) | `0x30E1`, `0x30F0` | medium | User-visible off/on commands are identified; exact internal flag bytes still need naming. |
| Color input command (`ESC K n`) | `0x2D27` | high | Parses ASCII color digit and writes `AA7A`. |
| Color command/status emission | `0x23AE` | medium | Routine emits `ESC K` plus a color digit; direction is output/diagnostic, not parser input. |
| Renderer metric tables | `0x4500/0x4600/0x45DC` | high | Character metric/width tables used during rendering. `0x41AD` is part of this path. |
| Font/character dot data | approx. `0x52D8-0x7FBF` | high | Dense character patterns; full listing decodes it as code if not marked data. |

## Next Reverse-Engineering Steps

1. Name the receive queue and current-character variables around `AA00`, `AA04`, `AA64`, `AA66`, `AA68`, and `A8C4-A8C6`.
2. Finish the remaining control-behavior details that can affect output: the external purpose of the undocumented `CTRL-]` vertical-format parser and its `C@` early-return form.
3. Convert the full listing into a commented disassembly with explicit data ranges for strings, ESC table data, the `0x28B0` control table, metrics, and fonts, so table decoding stops polluting code analysis.
4. Finish the remaining hardware-layer paper details: name the internal paper-out sensor flag bits behind `ESC O`/`ESC o`, and decide whether command-level emulation needs the low-level paper-feed motor scheduler/port timing beyond the queued feed records already mapped.
