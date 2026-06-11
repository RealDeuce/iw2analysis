# Apple ImageWriter II ROM analysis

This repository contains working reverse-engineering notes, disassembly
output, schematics, and reference documents for the Apple ImageWriter II
printer firmware.

It exists to support ImageWriter II printer emulation in Dreamulator:

https://github.com/RealDeuce/Dreamulator/

The goal is not to create a generic ImageWriter document archive.  The goal is
to keep the evidence needed to implement a ROM-derived ImageWriter II output
path: resident fonts, pitch selection, print effects, custom-character behavior,
graphics modes, paper motion, DIP/software switch behavior, serial buffering,
and command dispatch details.

## Why this exists

Dreamulator already has printer output paths for other printers where the
rendering behavior is derived from the original device rather than from a
generic substitute font.  The ImageWriter II should follow the same model.

The ImageWriter II firmware ROM and manuals contain enough printer behavior to
identify:

- the command parser and control-character dispatch paths;
- serial receive/transmit buffering and deferred command execution;
- pica, elite, ultracondensed, extended, semicondensed, and proportional pitch
  behavior;
- draft, correspondence, and near-letter-quality font selection;
- bold, double-width, half-height, underline, subscript, superscript, slashed
  zero, and overprint behavior;
- custom-character loading and high-ASCII/eighth-bit handling;
- graphics commands, repeat graphics, dot-column positioning, and
  double-width/bold graphics interactions;
- paper feed, form length, perforation skip, and reverse-feed state;
- startup, self-test, loopback-test, DIP switch, and software-switch behavior;
- service-level hardware details for the older ImageWriter II and later
  ImageWriter II/L boards.

Keeping the disassembly, source manuals, schematics, and trace notes together
makes the Dreamulator implementation reproducible.  When the emulator
needs a behavioral detail, this repository should show whether that detail is
already known, where it came from, and which ROM offsets are useful for
confirming it.

## Repository contents

| Path | Purpose |
| --- | --- |
| `disasm/iw2_upd7810_full.lst` | Full `upd7810` disassembly listing generated from the ROM. |
| `docs/firmware-map.md` | Firmware map with ROM identity, CPU evidence, memory/I/O observations, entry points, self-test strings, and current reverse-engineering status. |
| `docs/imagewriter-ii-command-reference.md` | Emulation-oriented command reference extracted from the Apple manuals and normalized against ROM behavior. |
| `docs/rom-command-map.md` | ROM-linked command map tying controls and ESC commands to parser tables, handlers, state bytes, and confidence notes. |
| `docs/service-source-notes.md` | Hardware and service notes from Apple Service Source and Sams Computerfacts documents. |
| `Apple ImageWriter II Technical Reference Manual.pdf` | Programmer reference for command bytes, defaults, switch semantics, graphics, and character-set behavior. |
| `Apple_Image_Writer_II_Owners_Manual_text.pdf` | Owner's manual text PDF used for user-visible behavior and command descriptions. |
| `Apple Technical Procedures ImageWriter II.pdf` | Apple service/procedure reference. |
| `Service_Source_Imagewriter_II.pdf` | Apple Service Source for ImageWriter II/L hardware and diagnostics. |
| `Sams_Technical_Imagewriter_II.pdf` | Sams Computerfacts service data for the older ImageWriter II logic board. |
| `Apple Dot Matrix Printer, ImageWriter I, Scribe - text font samples [300dpi].pdf` | Font/output sample reference for related Apple dot-matrix printers. |
| `IW-Schematic/` | ImageWriter schematic PDF pages. |

## ROM summary

The firmware image analyzed here is a 32768-byte ROM (`ImageWriter2_new.bin`,
not included in this repository) with:

- `cksum`: `3282235718 32768`
- SHA-256:
  `06f6e22c4bce0540ce3f29579086e90babdce0913028917a152ef9d6bcdb0f41`

The ROM disassembles coherently as NEC uPD7810-family code:

```sh
../mame/unidasm ImageWriter2_new.bin -arch upd7810 -basepc 0 -count 0x8000 > disasm/iw2_upd7810_full.lst
```

The service manuals use Apple/custom part numbers rather than a public CPU part
number.  Sams identifies the older board CPU as `EC-A056`; Apple Service Source
for the ImageWriter II/L identifies the CPU as `IC8`.  The `upd7810`
disassembly is still the best current architectural match.

## Key firmware structures

The main command/control loop starts at `0x2748`.  It fetches bytes from the
buffered parser path, special-cases backspace, and dispatches low controls
through the keyed table at `0x28B0-0x28D6`.

The post-`ESC` dispatcher is at `0x2C07`.  It bounds command bytes to
`0x21-0x7A`, uses the table at `0x2C1B`, and calls the selected handler through
the ROM's table-call mechanism.

Useful anchors already identified include:

- `0x2102`: serial interrupt entry;
- `0x2137`: serial receive buffer append;
- `0x217A`: self-ID response staging for `ESC ?`;
- `0x21DC`: serial transmit one byte;
- `0x2748`: main command/control loop;
- `0x28B0-0x28D6`: low-control dispatch table;
- `0x2C07`: post-`ESC` command dispatcher;
- `0x2D27`: `ESC K n` color-selection input handler;
- `0x302A`: `ESC D` software-switch set handler;
- `0x3065`: `ESC Z` software-switch clear handler;
- `0x368C`: backspace/overprint handler;
- `0x37C8`: current-line erase handler;
- `0x3DDD`, `0x3DF5`, `0x3DFE`, `0x3E07`, `0x3B8C`: paper-feed record
  builders;
- `0x4500`, `0x4600`, `0x45DC`: renderer metric tables;
- approximately `0x52D8-0x7FBF`: dense font/character dot data.

See `docs/firmware-map.md` and `docs/rom-command-map.md` before starting new
traces; many parser and output behaviors are already tied to ROM addresses.

## Command behavior

`docs/imagewriter-ii-command-reference.md` is the user-visible command reference.
`docs/rom-command-map.md` is the ROM-derived implementation map.

Useful command areas already traced include:

- low controls such as bell, backspace, horizontal tab, line feed, form feed,
  carriage return, double-width on/off, deselect, erase current line, and
  blank-line feed;
- the conditional high-bit behavior for `0x80-0x9F`, controlled by the
  eighth-bit software switch;
- `CTRL-H` overprint behavior, where the following byte is rendered at the
  backed-up position;
- `CTRL-X` current-line erase behavior, which clears only the not-yet-printed
  staged line;
- `CTRL-]`, an undocumented vertical-format/setup parser;
- font and pitch commands, including draft/correspondence/NLQ selection and
  proportional pitch modes;
- text effects such as underline, bold, double-width, half-height,
  subscript/superscript, and slashed zero;
- custom-character selection and loading commands;
- graphics commands `ESC G`, `ESC S`, `ESC g`, `ESC V`, and graphics positioning
  through `ESC F`;
- software switch mutation through `ESC D` and `ESC Z`;
- page length, top-of-form, feed direction, perforation skip, and paper-out
  sensor commands.

## Hardware and service notes

The service literature covers related but not identical hardware revisions.
Keep those distinctions when using IC numbers:

- Apple Service Source for ImageWriter II/L names ROM as `IC10`, RAM as `IC9`,
  CPU as `IC8`, and the gate array as `IC4`.
- Sams Computerfacts for the older ImageWriter II board names CPU `IC9` as
  Apple part `EC-A056`, ROM `IC10` as `04168C-15`, clock/RAM control `IC5` as
  `EC-A042`, and head/carrier motor control `IC6` as `EC-A041` / `2106AF001`.

Both service sources are useful for self-test, loopback, DIP switch, serial
interface, clock, reset, and board-role details.  The consolidated notes are in
`docs/service-source-notes.md`.

## How this should be used by Dreamulator work

Use this repository as the evidence pack for the ImageWriter II implementation:

1. Obtain the canonical firmware image (`ImageWriter2_new.bin`, see ROM
   summary above for checksums).
2. Use `disasm/iw2_upd7810_full.lst` and `docs/firmware-map.md` for ROM entry
   points, memory/state observations, and hardware anchors.
3. Use `docs/imagewriter-ii-command-reference.md` for programmer-visible command
   behavior.
4. Use `docs/rom-command-map.md` for dispatch addresses, handler traces, and
   ROM-derived confidence notes.
5. Use `docs/service-source-notes.md` and the service PDFs for board-level
   details, diagnostics, DIP switches, and hardware behavior.
6. When a new emulator behavior is unclear, add the new trace and derived output
   here first, then port the behavior into Dreamulator.

The desired end state in Dreamulator is an ImageWriter II output path whose
glyphs, command behavior, and paper/graphics semantics come from this ROM
analysis rather than from host fonts or approximations.
